import re
from typing import Any

from httpx import HTTPStatusError
from pasarguard import PasarguardAPI

from app.logger import get_logger
from app.services.users.identifiers import generate_username
from app.telegram.keyboards.buy import buy_cancel_button, buy_retry_username_button
from app.telegram.state import set_step
from app.utils.text.bot_texts import get_bot_text

logger = get_logger(__name__)

USERNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_]{1,30}[A-Za-z0-9]$")

PANEL_USERNAME_CONFLICT_CODES = frozenset((409, 400, 422))


def is_valid_username(name: str) -> bool:
    return bool(USERNAME_RE.fullmatch(name))


class UsernameLookupError(Exception):
    """The panel could not confirm whether a username is free, so it must not be used."""


async def is_username_free(panel: Any, username: str) -> bool:
    """True when the panel reports the username missing (404), False when it already exists.

    Any other outcome (non-404 HTTP status, network error, ...) raises :class:`UsernameLookupError`
    so callers fail closed instead of treating an unverified name as available.
    """
    try:
        await PasarguardAPI(panel.base_url).get_user_by_username(username=username, token=panel.cookie)
    except HTTPStatusError as e:
        if e.response.status_code == 404:
            return True
        logger.warning("Username lookup failed on panel %s (HTTP %s)", panel.code, e.response.status_code)
        raise UsernameLookupError(f"HTTP {e.response.status_code}") from e
    except Exception as e:
        logger.exception("Username lookup failed on panel %s", panel.code)
        raise UsernameLookupError(type(e).__name__) from e
    return False


async def generate_unique_username(panel: Any) -> str:
    """A random username the panel reports as free; raises :class:`UsernameLookupError` if it cannot check."""
    username = generate_username()
    for _ in range(5):
        if await is_username_free(panel, username):
            break
        username = generate_username()
    return username


async def username_check_failed_text() -> str:
    """Bot text telling the user the panel could not verify the name and they should retry."""
    return await get_bot_text(
        key="buy_username_check_failed",
        default="❌ بررسی نام کانفیگ در پنل ممکن نشد؛ لطفاً کمی بعد دوباره تلاش کنید.",
        lang="fa",
    )


def is_panel_username_conflict(exc: BaseException) -> bool:
    return isinstance(exc, HTTPStatusError) and exc.response.status_code in PANEL_USERNAME_CONFLICT_CODES


async def handle_buy_username_conflict(event, username: str) -> None:
    alert_text = await get_bot_text(
        key="buy_username_conflict_alert",
        default="نام «{username}» قبلاً در پنل ثبت شده است.",
        lang="fa",
    )
    conflict_text = await get_bot_text(
        key="buy_username_conflict_message",
        default=(
            "❌ **نام کانفیگ `{username}` تکراری است**\n\n"
            "این نام قبلاً توسط ادمین دیگری در پنل ساخته شده است.\n"
            "لطفاً با دکمه زیر نام دیگری انتخاب کنید."
        ),
        lang="fa",
    )
    await event.answer(alert_text.replace("{username}", username), alert=True)
    await event.edit(
        conflict_text.replace("{username}", username),
        buttons=[
            [await buy_retry_username_button()],
            [await buy_cancel_button("DataCancel")],
        ],
        parse_mode="md",
        link_preview=False,
    )
    await set_step(event.sender_id, "enter_username")
