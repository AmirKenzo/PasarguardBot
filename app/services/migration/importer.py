"""Resolves a ParsedMigration against live Pasargard panels, then commits it.

Split into two phases on purpose, so an admin can see real numbers before anything is
written:

- `resolve_migration` is read-only against our own DB (existence checks only) and
  authenticates + queries each source panel live, to find out exactly how many of the
  dump's services the panel still confirms exist (old bots in this domain are known to
  leave stale "active" rows behind after deleting the config only on the panel side).
- `commit_migration` writes what `resolve_migration` already found — it does not
  re-query the panels, so the numbers the admin approved are exactly what gets created.

Users are matched by Telegram id, panels by base_url, services by panel username —
anything already present is skipped rather than overwritten.
"""

from __future__ import annotations

import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Literal

from httpx import HTTPStatusError
from sqlalchemy import select

from app.db.base import AsyncSessionLocal as Session
from app.db.crud.panels import PanelsManager
from app.db.crud.services import ServiceCRUD
from app.db.models.services import Service
from app.db.models.user import User
from app.logger import get_logger
from app.services.migration.base import ParsedMigration, ParsedPanel, ParsedService
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
PanelStatus = Literal["existing", "ok", "login_failed"]


async def _report(progress_cb: ProgressCallback, text: str) -> None:
    if progress_cb is not None:
        await progress_cb(text)


def _unique_code(existing: set[int], low: int, high: int) -> int:
    for _ in range(50):
        code = random.randint(low, high)
        if code not in existing:
            existing.add(code)
            return code
    raise RuntimeError("Could not allocate a unique code after 50 attempts.")


def _resolve_expire(value) -> int | None:
    if value is None:
        return None
    if hasattr(value, "timestamp"):
        return int(value.timestamp())
    return int(value)


async def _existing_user_ids(telegram_ids: list[int]) -> set[int]:
    existing: set[int] = set()
    async with Session() as session:
        for start in range(0, len(telegram_ids), _DB_BATCH_SIZE):
            batch = telegram_ids[start : start + _DB_BATCH_SIZE]
            rows = await session.execute(select(User.id).where(User.id.in_(batch)))
            existing.update(rows.scalars().all())
    return existing


async def _existing_service_usernames(candidates: list[str]) -> set[str]:
    existing: set[str] = set()
    for start in range(0, len(candidates), _DB_BATCH_SIZE):
        batch = candidates[start : start + _DB_BATCH_SIZE]
        rows = await ServiceCRUD().get_services_by_usernames(batch)
        existing.update(row.username for row in rows)
    return existing


@dataclass(slots=True)
class _EphemeralPanel:
    """A panel that authenticated successfully but has no DB row (and thus no `code`) yet."""

    base_url: str
    cookie: str
    auth_type: str = "password"
    code: int | None = None


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
            if exc.response.status_code != 401 or getattr(panel, "code", None) is None:
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


@dataclass(slots=True)
class ResolvedPanel:
    source_panel: ParsedPanel
    services: list[ParsedService] = field(default_factory=list)
    status: PanelStatus = "login_failed"
    db_panel: object | None = None
    token: str | None = None
    login_error: str | None = None
    already_in_db: set[str] = field(default_factory=set)
    matched_users: dict[str, object] = field(default_factory=dict)

    @property
    def services_dump_count(self) -> int:
        return len(self.services)

    @property
    def services_matched_count(self) -> int:
        return sum(
            1
            for s in self.services
            if any(c in self.already_in_db for c in s.username_candidates)
            or any(c in self.matched_users for c in s.username_candidates)
        )


@dataclass(slots=True)
class ResolvedMigration:
    parsed: ParsedMigration
    users_new: int = 0
    users_existing: int = 0
    services_inactive_in_source: int = 0
    panels: list[ResolvedPanel] = field(default_factory=list)

    @property
    def services_dump_total(self) -> int:
        return sum(p.services_dump_count for p in self.panels)

    @property
    def services_matched_total(self) -> int:
        return sum(p.services_matched_count for p in self.panels)


async def _resolve_panel(source_panel: ParsedPanel, services: list[ParsedService], existing_by_url: dict[str, object]):
    rp = ResolvedPanel(source_panel=source_panel, services=services)

    existing_db_panel = existing_by_url.get(source_panel.base_url.rstrip("/"))
    if existing_db_panel is not None:
        rp.status = "existing"
        rp.db_panel = existing_db_panel
        rp.token = existing_db_panel.cookie
        panel_for_lookup = existing_db_panel
    else:
        try:
            _authed, token, _groups = await verify_panel_password(
                source_panel.base_url, source_panel.username, source_panel.password
            )
        except Exception as exc:
            rp.login_error = format_exception_message(exc)
            return rp
        rp.status = "ok"
        rp.token = token
        panel_for_lookup = _EphemeralPanel(base_url=source_panel.base_url, cookie=token)

    if services:
        all_candidates = sorted({c for s in services for c in s.username_candidates})
        rp.already_in_db = await _existing_service_usernames(all_candidates)
        to_query = sorted({c for c in all_candidates if c not in rp.already_in_db})
        rp.matched_users = await _fetch_panel_users(panel_for_lookup, to_query)

    return rp


async def resolve_migration(parsed: ParsedMigration, *, progress_cb: ProgressCallback = None) -> ResolvedMigration:
    resolved = ResolvedMigration(parsed=parsed)

    telegram_ids = [u.telegram_id for u in parsed.users]
    existing_ids = await _existing_user_ids(telegram_ids)
    resolved.users_new = sum(1 for tid in telegram_ids if tid not in existing_ids)
    resolved.users_existing = len(telegram_ids) - resolved.users_new

    active_services = [s for s in parsed.services if s.enabled]
    resolved.services_inactive_in_source = len(parsed.services) - len(active_services)

    by_panel: dict[str, list[ParsedService]] = {}
    for service in active_services:
        by_panel.setdefault(service.source_panel_id, []).append(service)

    existing_by_url = {p.base_url.rstrip("/"): p for p in await PanelsManager().get_all_panels()}

    for source_panel in parsed.panels:
        rp = await _resolve_panel(source_panel, by_panel.get(source_panel.source_id, []), existing_by_url)
        resolved.panels.append(rp)
        if rp.status == "login_failed":
            await _report(progress_cb, f"❌ ورود به پنل {source_panel.base_url} ناموفق بود.")
        else:
            await _report(
                progress_cb,
                f"🔎 {source_panel.name}: {rp.services_matched_count}/{rp.services_dump_count} سرویس یافت شد.",
            )

    return resolved


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
    services_inactive_in_source: int = 0
    issues: list[str] = field(default_factory=list)

    def add_issue(self, text: str) -> None:
        self.issues.append(text)
        del self.issues[:-_MAX_ISSUES]


async def _commit_users(resolved: ResolvedMigration, result: ImportResult, progress_cb: ProgressCallback) -> None:
    existing_ids = await _existing_user_ids([u.telegram_id for u in resolved.parsed.users])
    to_create = [u for u in resolved.parsed.users if u.telegram_id not in existing_ids]
    result.users_skipped = len(resolved.parsed.users) - len(to_create)

    async with Session() as session:
        for start in range(0, len(to_create), _DB_BATCH_SIZE):
            batch = to_create[start : start + _DB_BATCH_SIZE]
            session.add_all(User(id=u.telegram_id, amount=u.amount, time_s=u.time_s, language="fa") for u in batch)
            await session.commit()
            result.users_created += len(batch)
            await _report(progress_cb, f"👥 کاربران وارد شده: {result.users_created}/{len(to_create)}")


async def _commit_panel(
    rp: ResolvedPanel, existing_codes: set[int], result: ImportResult, progress_cb: ProgressCallback
):
    if rp.status == "existing":
        result.panels_skipped_existing += 1
        return rp.db_panel

    if rp.status == "login_failed":
        result.panels_failed_login += 1
        result.add_issue(f"پنل {rp.source_panel.base_url}: ورود ناموفق ({rp.login_error})")
        return None

    code = _unique_code(existing_codes, 10000, 99999)
    new_panel = await PanelsManager().add_panel(
        code=code,
        name=rp.source_panel.name,
        enable=True,
        base_url=rp.source_panel.base_url,
        username=rp.source_panel.username,
        password=encrypt_data(rp.source_panel.password),
        cookie=rp.token,
        auth_type="password",
    )
    result.panels_created += 1
    await _report(progress_cb, f"🖥 پنل ایجاد شد: {rp.source_panel.base_url}")
    return new_panel


async def _commit_services_for_panel(
    rp: ResolvedPanel, panel, existing_service_codes: set[int], result: ImportResult, progress_cb: ProgressCallback
) -> None:
    for service in rp.services:
        if any(c in rp.already_in_db for c in service.username_candidates):
            result.services_skipped_existing += 1
            continue

        matched_username = next((c for c in service.username_candidates if c in rp.matched_users), None)
        if matched_username is None:
            result.services_unmatched_on_panel += 1
            continue

        matched_user = rp.matched_users[matched_username]
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

        rp.already_in_db.add(matched_username)
        result.services_created += 1
        if result.services_created % 200 == 0:
            await _report(progress_cb, f"🧩 سرویس‌های وارد شده: {result.services_created}")


async def commit_migration(resolved: ResolvedMigration, *, progress_cb: ProgressCallback = None) -> ImportResult:
    result = ImportResult()
    result.services_inactive_in_source = resolved.services_inactive_in_source
    await _commit_users(resolved, result, progress_cb)

    async with Session() as session:
        rows = await session.execute(select(Service.code))
        existing_service_codes = set(rows.scalars().all())
    existing_panel_codes = {p.code for p in await PanelsManager().get_all_panels()}

    for rp in resolved.panels:
        panel = await _commit_panel(rp, existing_panel_codes, result, progress_cb)
        if panel is not None:
            await _commit_services_for_panel(rp, panel, existing_service_codes, result, progress_cb)

    return result
