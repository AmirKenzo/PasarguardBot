import asyncio
import contextlib

from httpx import HTTPStatusError, RequestError, TimeoutException
from pasarguard import GroupsResponse, GroupsSimpleResponse, PasarguardAPI
from pydantic import ValidationError

from app.db.crud.panels import PanelsManager
from app.services.panels.cookies import format_panel_cookie_validity, panel_cookie_needs_refresh
from app.utils.security.crypto import decrypt_data

AUTH_PASSWORD = "password"
AUTH_API_KEY = "api_key"
PANEL_AUTH_PLACEHOLDER_USERNAME = "-"

_GROUPS_FALLBACK_STATUSES = frozenset({403, 404, 405})

PanelGroupsResponse = GroupsResponse | GroupsSimpleResponse

_panel_refresh_locks: dict[int, asyncio.Lock] = {}
_panel_refresh_locks_guard = asyncio.Lock()


def panel_uses_api_key(panel) -> bool:
    if getattr(panel, "auth_type", None) == AUTH_API_KEY:
        return True
    return (panel.cookie or "").strip().startswith("pg_key_")


def panel_needs_cookie_refresh(panel) -> bool:
    if panel_uses_api_key(panel):
        return False
    return panel_cookie_needs_refresh(panel.cookie)


def create_panel_api(panel) -> PasarguardAPI:
    if panel_uses_api_key(panel):
        return PasarguardAPI(base_url=panel.base_url, api_key=panel.cookie)
    return PasarguardAPI(base_url=panel.base_url, token=panel.cookie)


async def fetch_panel_groups(api: PasarguardAPI) -> PanelGroupsResponse:
    """Prefer lightweight /api/groups/simple; fall back to full list if needed."""
    try:
        return await api.get_groups_simple(all=True)
    except HTTPStatusError as e:
        if e.response.status_code in _GROUPS_FALLBACK_STATUSES:
            return await api.get_all_groups()
        raise


async def verify_panel_api_key(base_url, api_key) -> tuple[PasarguardAPI, PanelGroupsResponse]:
    api = PasarguardAPI(base_url=base_url, api_key=api_key.strip())
    groups = await fetch_panel_groups(api)
    return api, groups


async def verify_panel_password(base_url, username, password):
    api = PasarguardAPI(base_url=base_url)
    token = await api.get_token(username=username.strip(), password=password.strip())
    authed = PasarguardAPI(base_url=base_url, token=token.access_token)
    groups = await fetch_panel_groups(authed)
    return authed, token.access_token, groups


async def _lock_for_panel(panel_code: int) -> asyncio.Lock:
    async with _panel_refresh_locks_guard:
        lock = _panel_refresh_locks.get(panel_code)
        if lock is None:
            lock = asyncio.Lock()
            _panel_refresh_locks[panel_code] = lock
        return lock


async def refresh_panel_cookie(panel) -> str:
    if panel_uses_api_key(panel):
        return panel.cookie
    lock = await _lock_for_panel(int(panel.code))
    async with lock:
        # Another waiter may have already refreshed while we queued for the lock.
        fresh = await PanelsManager().get_panel_by_code(panel.code)
        if fresh and fresh.cookie and fresh.cookie != panel.cookie:
            panel.cookie = fresh.cookie
            return fresh.cookie

        api = PasarguardAPI(base_url=panel.base_url)
        token = await api.get_token(username=panel.username, password=decrypt_data(panel.password))
        panel.cookie = token.access_token
        await PanelsManager().update_panel(code=panel.code, cookie=token.access_token)
        return token.access_token


async def fetch_panel_groups_with_auth(panel) -> PanelGroupsResponse:
    api = create_panel_api(panel)
    try:
        return await fetch_panel_groups(api)
    except HTTPStatusError as e:
        if e.response.status_code == 401 and not panel_uses_api_key(panel):
            cookie = await refresh_panel_cookie(panel)
            return await fetch_panel_groups(PasarguardAPI(base_url=panel.base_url, token=cookie))
        raise


def format_panel_refresh_status(panel, *, locale="fa") -> str:
    if panel_uses_api_key(panel):
        return "api_key (no refresh)" if locale == "en" else "API Key (بدون نیاز به refresh)"
    return format_panel_cookie_validity(panel.cookie, locale=locale)


def panel_auth_type_label(panel, *, short=False) -> str:
    if panel_uses_api_key(panel):
        return "API Key" if short else "🔑 API Key"
    return "User/Pass" if short else "👤 Username & Password"


def format_exception_message(exc: BaseException) -> str:
    """Build a non-empty error string (type, message, and cause when needed)."""
    parts: list[str] = []
    message = str(exc).strip()
    parts.append(message or type(exc).__name__)

    cause = exc.__cause__ or exc.__context__
    if isinstance(cause, BaseException) and cause is not exc:
        cause_msg = str(cause).strip() or type(cause).__name__
        if cause_msg and cause_msg not in message:
            parts.append(f"caused by {type(cause).__name__}: {cause_msg}")

    # httpx.RequestError.request raises RuntimeError when unset; use _request.
    request = getattr(exc, "_request", None)
    if request is not None:
        with contextlib.suppress(Exception):
            parts.append(f"{request.method} {request.url}")

    return " | ".join(parts)


def panel_api_error_text(exc: BaseException) -> str:
    """English Telegram message for panel connect/auth/API failures."""
    if isinstance(exc, HTTPStatusError):
        status = exc.response.status_code
        if status == 401:
            return "Error: Unauthorized. Check username/password or API Key."
        if status == 403:
            return "Error: Forbidden (403). Check admin permissions."
        if status == 404:
            return "Error: Panel URL or API path not found (404)."
        body = (exc.response.text or "").strip()
        detail = body[:200] if body else format_exception_message(exc)
        return f"HTTP error from panel ({status}): {detail}"

    if isinstance(exc, TimeoutException):
        return "Error: Panel connection timed out. Check panel URL and network access."

    if isinstance(exc, RequestError):
        return f"Error: Could not connect to panel. {format_exception_message(exc)}"

    if isinstance(exc, ValidationError):
        return f"Error: Unexpected panel response format. {format_exception_message(exc)}"

    if isinstance(exc, ValueError):
        return f"Error: {format_exception_message(exc)}"

    return f"An unexpected error occurred: {format_exception_message(exc)}"
