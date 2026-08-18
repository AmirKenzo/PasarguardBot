"""Executes a ParsedMigration against this bot's own database and Pasargard panels.

Users are matched by Telegram id, panels by base_url, services by panel username —
anything already present is skipped rather than overwritten, so re-running an import
(e.g. after fixing a panel login) is safe. Service data (expiry, data limit, enabled
state, panel_userid) is always read live from the panel rather than trusted from the
old bot's database, so only configs the panel still confirms are imported.
"""

from __future__ import annotations

import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from httpx import HTTPStatusError
from sqlalchemy import select

from app.db.base import AsyncSessionLocal as Session
from app.db.crud.panels import PanelsManager
from app.db.crud.services import ServiceCRUD
from app.db.models.services import Service
from app.db.models.user import User
from app.logger import get_logger
from app.services.migration.base import ParsedMigration, ParsedPanel
from app.services.panels.auth import (
    create_panel_api,
    format_exception_message,
    refresh_panel_cookie,
    verify_panel_password,
)
from app.utils.security.crypto import encrypt_data

logger = get_logger(__name__)

_DB_BATCH_SIZE = 500
_PANEL_QUERY_CHUNK = 100
_MAX_ISSUES = 20

ProgressCallback = Callable[[str], Awaitable[None]] | None


@dataclass(slots=True)
class ImportResult:
    users_created: int = 0
    users_skipped: int = 0
    panels_created: int = 0
    panels_skipped_existing: int = 0
    panels_failed_login: int = 0
    services_created: int = 0
    services_skipped_existing: int = 0
    services_unmatched_on_panel: int = 0
    issues: list[str] = field(default_factory=list)

    def add_issue(self, text: str) -> None:
        self.issues.append(text)
        del self.issues[:-_MAX_ISSUES]


async def _report(progress_cb: ProgressCallback, text: str) -> None:
    if progress_cb is not None:
        await progress_cb(text)


async def _import_users(parsed: ParsedMigration, result: ImportResult, progress_cb: ProgressCallback) -> None:
    ids = [u.telegram_id for u in parsed.users]
    existing_ids: set[int] = set()
    async with Session() as session:
        for start in range(0, len(ids), _DB_BATCH_SIZE):
            batch = ids[start : start + _DB_BATCH_SIZE]
            rows = await session.execute(select(User.id).where(User.id.in_(batch)))
            existing_ids.update(rows.scalars().all())

    to_create = [u for u in parsed.users if u.telegram_id not in existing_ids]
    result.users_skipped = len(parsed.users) - len(to_create)

    async with Session() as session:
        for start in range(0, len(to_create), _DB_BATCH_SIZE):
            batch = to_create[start : start + _DB_BATCH_SIZE]
            session.add_all(User(id=u.telegram_id, amount=u.amount, time_s=u.time_s, language="fa") for u in batch)
            await session.commit()
            result.users_created += len(batch)
            await _report(progress_cb, f"👥 کاربران وارد شده: {result.users_created}/{len(to_create)}")


def _unique_code(existing: set[int], low: int, high: int) -> int:
    for _ in range(50):
        code = random.randint(low, high)
        if code not in existing:
            existing.add(code)
            return code
    raise RuntimeError("Could not allocate a unique code after 50 attempts.")


async def _create_panel(
    source_panel: ParsedPanel, existing_codes: set[int], result: ImportResult, progress_cb: ProgressCallback
):
    try:
        _authed, token, _groups = await verify_panel_password(
            source_panel.base_url, source_panel.username, source_panel.password
        )
    except Exception as exc:
        result.panels_failed_login += 1
        result.add_issue(f"پنل {source_panel.base_url}: ورود ناموفق ({format_exception_message(exc)})")
        await _report(progress_cb, f"❌ ورود به پنل {source_panel.base_url} ناموفق بود.")
        return None

    code = _unique_code(existing_codes, 10000, 99999)
    new_panel = await PanelsManager().add_panel(
        code=code,
        name=source_panel.name,
        enable=True,
        base_url=source_panel.base_url,
        username=source_panel.username,
        password=encrypt_data(source_panel.password),
        cookie=token,
        auth_type="password",
    )
    result.panels_created += 1
    await _report(progress_cb, f"🖥 پنل ایجاد شد: {source_panel.base_url}")
    return new_panel


async def _import_panels(
    parsed: ParsedMigration, result: ImportResult, progress_cb: ProgressCallback
) -> dict[str, object]:
    """Returns {source_panel_id: Panels row} for panels that now exist (created or already there)."""
    all_panels = await PanelsManager().get_all_panels()
    existing_by_url = {p.base_url.rstrip("/"): p for p in all_panels}
    existing_codes = {p.code for p in all_panels}

    accepted: dict[str, object] = {}
    for source_panel in parsed.panels:
        existing = existing_by_url.get(source_panel.base_url.rstrip("/"))
        if existing is not None:
            accepted[source_panel.source_id] = existing
            result.panels_skipped_existing += 1
            continue

        new_panel = await _create_panel(source_panel, existing_codes, result, progress_cb)
        if new_panel is not None:
            existing_by_url[source_panel.base_url.rstrip("/")] = new_panel
            accepted[source_panel.source_id] = new_panel

    return accepted


async def _fetch_panel_users(panel, usernames: list[str]) -> dict[str, object]:
    """Best-effort batch lookup; returns {username: UserResponse} for whichever usernames matched."""
    found: dict[str, object] = {}
    if not usernames:
        return found

    api = create_panel_api(panel)
    for start in range(0, len(usernames), _PANEL_QUERY_CHUNK):
        chunk = usernames[start : start + _PANEL_QUERY_CHUNK]
        try:
            resp = await api.get_users(token=panel.cookie, usernames=chunk, limit=len(chunk))
        except HTTPStatusError as exc:
            if exc.response.status_code != 401:
                logger.warning("Migration: panel get_users chunk failed: %s", format_exception_message(exc))
                continue
            try:
                cookie = await refresh_panel_cookie(panel)
                resp = await create_panel_api(panel).get_users(token=cookie, usernames=chunk, limit=len(chunk))
            except Exception as retry_exc:
                logger.warning("Migration: panel get_users retry failed: %s", format_exception_message(retry_exc))
                continue
        except Exception as exc:
            logger.warning("Migration: panel get_users chunk failed: %s", format_exception_message(exc))
            continue
        for user in resp.users:
            found[user.username] = user
    return found


def _resolve_expire(value) -> int | None:
    if value is None:
        return None
    if hasattr(value, "timestamp"):
        return int(value.timestamp())
    return int(value)


async def _existing_service_usernames(candidates: list[str]) -> set[str]:
    existing: set[str] = set()
    for start in range(0, len(candidates), _DB_BATCH_SIZE):
        batch = candidates[start : start + _DB_BATCH_SIZE]
        rows = await ServiceCRUD().get_services_by_usernames(batch)
        existing.update(row.username for row in rows)
    return existing


async def _import_services(
    parsed: ParsedMigration,
    panels_by_source_id: dict[str, object],
    result: ImportResult,
    progress_cb: ProgressCallback,
) -> None:
    relevant = [s for s in parsed.services if s.source_panel_id in panels_by_source_id]
    if not relevant:
        return

    async with Session() as session:
        rows = await session.execute(select(Service.code))
        existing_service_codes = set(rows.scalars().all())

    by_panel: dict[str, list] = {}
    for service in relevant:
        by_panel.setdefault(service.source_panel_id, []).append(service)

    for source_panel_id, services in by_panel.items():
        panel = panels_by_source_id[source_panel_id]
        all_candidates = sorted({c for s in services for c in s.username_candidates})
        existing_usernames = await _existing_service_usernames(all_candidates)

        to_query = sorted({c for c in all_candidates if c not in existing_usernames})
        panel_users = await _fetch_panel_users(panel, to_query)

        for service in services:
            if any(c in existing_usernames for c in service.username_candidates):
                result.services_skipped_existing += 1
                continue

            matched_username = next((c for c in service.username_candidates if c in panel_users), None)
            if matched_username is None:
                result.services_unmatched_on_panel += 1
                continue

            matched_user = panel_users[matched_username]
            code = _unique_code(existing_service_codes, 10000, 9999999)
            ok, msg = await ServiceCRUD().create_service(
                code=code,
                username=matched_username,
                enable=str(matched_user.status) == "active",
                in_panel=panel.code,
                panel_userid=matched_user.id,
                id=service.owner_id,
                package_size=matched_user.data_limit,
                createtime=service.created_at,
                expiration_time=_resolve_expire(matched_user.expire),
            )
            if not ok:
                result.add_issue(f"سرویس {matched_username}: {msg}")
                continue

            existing_usernames.add(matched_username)
            result.services_created += 1
            if result.services_created % 200 == 0:
                await _report(progress_cb, f"🧩 سرویس‌های وارد شده: {result.services_created}")


async def run_import(parsed: ParsedMigration, *, progress_cb: ProgressCallback = None) -> ImportResult:
    result = ImportResult()
    await _import_users(parsed, result, progress_cb)
    panels_by_source_id = await _import_panels(parsed, result, progress_cb)
    await _import_services(parsed, panels_by_source_id, result, progress_cb)
    return result
