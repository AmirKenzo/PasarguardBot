"""Move a panel admin's active users onto another admin and record them as bot services.

The flow is split into read-only steps (access check, admin list, preview) and a
background job that changes ownership on the panel with ``bulk_set_owner`` and
creates one ``Service`` row per moved user for the target Telegram id.

Only users whose panel status is ``active`` are moved. The source admin itself is
never modified. Users already recorded in the bot for a different Telegram id are
skipped and reported as conflicts, so no existing service changes hands silently.
"""

from __future__ import annotations

import asyncio
import csv
import io
import random
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Literal

from httpx import HTTPStatusError
from pasarguard import BulkUsersSetOwner, PasarguardAPI, PermissionScope

from app import Kenzo
from app.db.crud.services import ServiceCRUD
from app.logger import LogType, get_logger
from app.services.panels.admins import list_panel_admins
from app.services.panels.auth import (
    create_panel_api,
    format_exception_message,
    panel_uses_api_key,
    refresh_panel_cookie,
)
from app.telegram.shared.utils.logging import send_log_message

log = get_logger(__name__)

_USERS_PAGE_SIZE = 500
_SET_OWNER_CHUNK = 100
_DB_BATCH_SIZE = 500
_JOB_TTL_SECONDS = 6 * 3600
_MAX_CONFLICTS_PREVIEW = 200

ACTIVE_STATUS = "active"

TransferResult = Literal["moved", "moved_linked", "moved_no_record", "failed", "conflict"]
JobState = Literal["running", "done", "error"]


class TransferError(Exception):
    """A user-facing failure (Persian message) raised before anything is changed."""


async def _call(panel, operation):
    """Run ``operation(api, token)`` and retry once with a fresh cookie on 401."""
    api = create_panel_api(panel)
    try:
        return await operation(api, panel.cookie)
    except HTTPStatusError as exc:
        if exc.response.status_code == 401 and not panel_uses_api_key(panel):
            token = await refresh_panel_cookie(panel)
            return await operation(PasarguardAPI(base_url=panel.base_url, token=token), token)
        raise


def _scope_is_all(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return value is not None and int(value) == int(PermissionScope.ALL)


async def _current_admin(panel) -> Any:
    """The admin the bot is logged in as, or raise if it cannot move users."""
    try:
        me = await _call(panel, lambda api, token: api.get_current_admin(token=token))
    except Exception as exc:
        log.error("admin transfer: access check failed panel=%s: %s", panel.code, format_exception_message(exc))
        raise TransferError("اتصال به پنل برای بررسی دسترسی ناموفق بود.") from exc

    role = getattr(me, "role", None)
    if role is not None and getattr(role, "is_owner", False):
        return me

    permissions = getattr(role, "permissions", None) if role is not None else None
    users_perm = getattr(permissions, "users", None) if permissions is not None else None
    admins_perm = getattr(permissions, "admins", None) if permissions is not None else None
    has_full_access = (
        users_perm is not None
        and _scope_is_all(getattr(users_perm, "set_owner", None))
        and _scope_is_all(getattr(users_perm, "read", None))
        and admins_perm is not None
        and bool(getattr(admins_perm, "read", False))
    )
    if not has_full_access:
        raise TransferError(
            "اکانتی که ربات با آن به این پنل وصل است دسترسی اونر یا فول (خواندن همه یوزرها و تغییر مالک) ندارد."
        )
    return me


async def check_transfer_access(panel) -> str:
    """Return the username the bot is logged in as, or raise if it cannot move users."""
    return str((await _current_admin(panel)).username)


async def fetch_admin_users(panel, admin_username: str) -> list[Any]:
    """Every panel user owned by ``admin_username``, de-duplicated by id."""

    async def _fetch(api: PasarguardAPI, token: str) -> list[Any]:
        users: dict[int, Any] = {}
        offset = 0
        while True:
            resp = await api.get_users(token=token, admin=[admin_username], offset=offset, limit=_USERS_PAGE_SIZE)
            page = list(getattr(resp, "users", None) or [])
            for user in page:
                owner = getattr(getattr(user, "admin", None), "username", None)
                if owner is not None and str(owner) != admin_username:
                    continue
                users[int(user.id)] = user
            total = int(getattr(resp, "total", 0) or 0)
            offset += _USERS_PAGE_SIZE
            if not page or len(page) < _USERS_PAGE_SIZE or (total and offset >= total):
                break
        return list(users.values())

    return await _call(panel, _fetch)


def _status(user: Any) -> str:
    raw = getattr(user, "status", None)
    return str(getattr(raw, "value", raw) or "")


def _timestamp(value: Any) -> int | None:
    if value in (None, 0, ""):
        return None
    if hasattr(value, "timestamp"):
        return int(value.timestamp())
    try:
        parsed = int(value)
    except TypeError, ValueError:
        return None
    return parsed or None


def _reset_strategy(user: Any) -> str:
    raw = getattr(user, "data_limit_reset_strategy", None)
    return str(getattr(raw, "value", raw) or "no_reset")


async def _existing_services(panel_code: int, usernames: list[str]) -> dict[str, Any]:
    found: dict[str, Any] = {}
    for start in range(0, len(usernames), _DB_BATCH_SIZE):
        rows = await ServiceCRUD().get_services_by_panel_and_usernames(
            panel_code, usernames[start : start + _DB_BATCH_SIZE]
        )
        for row in rows:
            found[str(row.username)] = row
    return found


@dataclass(slots=True)
class AdminOption:
    username: str
    total_users: int
    status: str
    note: str | None
    suggested: bool


async def list_transfer_admins(panel, telegram_id: int) -> tuple[str, list[AdminOption]]:
    """Source candidates: every panel admin except the one the bot itself uses."""
    current = await check_transfer_access(panel)
    admins = await list_panel_admins(panel)
    options: list[AdminOption] = []
    for admin in admins:
        username = str(getattr(admin, "username", "") or "").strip()
        if not username or username == current:
            continue
        note = str(getattr(admin, "note", "") or "").strip() or None
        admin_tg = getattr(admin, "telegram_id", None)
        suggested = note == str(telegram_id) or (admin_tg is not None and int(admin_tg) == telegram_id)
        raw_status = getattr(admin, "status", None)
        options.append(
            AdminOption(
                username=username,
                total_users=int(getattr(admin, "total_users", 0) or 0),
                status=str(getattr(raw_status, "value", raw_status) or ""),
                note=note,
                suggested=suggested,
            )
        )
    options.sort(key=lambda item: (not item.suggested, -item.total_users, item.username.lower()))
    return current, options


@dataclass(slots=True)
class TransferPreview:
    target_admin: str
    total_users: int
    status_counts: dict[str, int]
    active_users: int
    will_create: int
    already_linked: int
    conflicts: list[dict[str, Any]]
    conflicts_total: int
    active_used_traffic: int
    active_data_limit: int
    active_unlimited: int


def _validate_admins(source_admin: str, target_admin: str) -> tuple[str, str]:
    source = (source_admin or "").strip()
    target = (target_admin or "").strip()
    if not source:
        raise TransferError("ادمین مبدأ را انتخاب کنید.")
    if not target:
        raise TransferError("ادمین مقصد مشخص نیست.")
    if source == target:
        raise TransferError("ادمین مبدأ و مقصد نمی‌توانند یکی باشند.")
    return source, target


async def _ensure_target_exists(panel, target_admin: str, current_admin: str) -> None:
    if target_admin == current_admin:
        return
    admins = await list_panel_admins(panel, usernames={target_admin})
    if not any(str(getattr(a, "username", "")) == target_admin for a in admins):
        raise TransferError("ادمین مقصد در پنل پیدا نشد.")


async def _resolve_admins(panel, source_admin: str, target_admin: str | None) -> tuple[str, str]:
    """Validate the pair; an empty target means the admin the bot itself uses on this panel."""
    current = await check_transfer_access(panel)
    source, target = _validate_admins(source_admin, (target_admin or "").strip() or current)
    await _ensure_target_exists(panel, target, current)
    return source, target


async def build_preview(
    panel, *, telegram_id: int, source_admin: str, target_admin: str | None = None
) -> TransferPreview:
    source, target = await _resolve_admins(panel, source_admin, target_admin)

    users = await fetch_admin_users(panel, source)
    status_counts = Counter(_status(user) or "unknown" for user in users)
    active = [user for user in users if _status(user) == ACTIVE_STATUS]
    existing = await _existing_services(int(panel.code), [str(user.username) for user in active])

    will_create = already_linked = 0
    conflicts: list[dict[str, Any]] = []
    used = limit = unlimited = 0
    for user in active:
        row = existing.get(str(user.username))
        if row is None:
            will_create += 1
        elif int(row.id or 0) == telegram_id:
            already_linked += 1
        else:
            conflicts.append({"username": str(user.username), "owner_id": int(row.id or 0)})
            continue
        used += int(getattr(user, "used_traffic", 0) or 0)
        data_limit = int(getattr(user, "data_limit", 0) or 0)
        if data_limit > 0:
            limit += data_limit
        else:
            unlimited += 1

    return TransferPreview(
        target_admin=target,
        total_users=len(users),
        status_counts=dict(status_counts),
        active_users=len(active),
        will_create=will_create,
        already_linked=already_linked,
        conflicts=conflicts[:_MAX_CONFLICTS_PREVIEW],
        conflicts_total=len(conflicts),
        active_used_traffic=used,
        active_data_limit=limit,
        active_unlimited=unlimited,
    )


@dataclass(slots=True)
class TransferRow:
    username: str
    panel_user_id: int
    result: TransferResult
    reason: str | None = None
    service_code: int | None = None


@dataclass(slots=True)
class TransferJob:
    id: str
    panel_code: int
    panel_name: str
    telegram_id: int
    source_admin: str
    target_admin: str
    actor_id: int
    notify: bool
    state: JobState = "running"
    phase: str = "fetch"
    total: int = 0
    processed: int = 0
    skipped_inactive: int = 0
    remaining_active_on_source: int | None = None
    error: str | None = None
    started_at: int = field(default_factory=lambda: int(time.time()))
    finished_at: int | None = None
    rows: list[TransferRow] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return dict(Counter(row.result for row in self.rows))


_jobs: dict[str, TransferJob] = {}
_running_keys: set[tuple[int, str]] = set()
_running_guard = asyncio.Lock()
_background_tasks: set[asyncio.Task] = set()


def _prune_jobs() -> None:
    cutoff = int(time.time()) - _JOB_TTL_SECONDS
    for job_id in [jid for jid, job in _jobs.items() if job.finished_at and job.finished_at < cutoff]:
        _jobs.pop(job_id, None)


def get_job(job_id: str) -> TransferJob | None:
    return _jobs.get(job_id)


async def start_transfer(
    panel,
    *,
    telegram_id: int,
    source_admin: str,
    target_admin: str | None,
    actor_id: int,
    notify: bool,
) -> TransferJob:
    source, target = await _resolve_admins(panel, source_admin, target_admin)

    key = (int(panel.code), source)
    async with _running_guard:
        if key in _running_keys:
            raise TransferError("انتقال یوزرهای این ادمین در حال اجراست.")
        _running_keys.add(key)

    _prune_jobs()
    job = TransferJob(
        id=uuid.uuid4().hex,
        panel_code=int(panel.code),
        panel_name=str(panel.name),
        telegram_id=telegram_id,
        source_admin=source,
        target_admin=target,
        actor_id=actor_id,
        notify=notify,
    )
    _jobs[job.id] = job

    task = asyncio.create_task(_run_job(panel, job, key))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return job


async def _run_job(panel, job: TransferJob, key: tuple[int, str]) -> None:
    try:
        await _execute(panel, job)
        job.state = "done"
    except Exception as exc:
        log.error("admin transfer job %s failed: %s", job.id, format_exception_message(exc), exc_info=True)
        job.state = "error"
        job.error = "انتقال با خطا متوقف شد؛ جزئیات در گزارش آمده است."
    finally:
        job.finished_at = int(time.time())
        async with _running_guard:
            _running_keys.discard(key)
        await _report(job)


async def _set_owner_chunk(panel, users: list[Any], target: str) -> dict[int, str | None]:
    """Return {panel_user_id: None on success | error reason}."""
    ids = [int(user.id) for user in users]
    by_username = {str(user.username): int(user.id) for user in users}
    outcome: dict[int, str | None] = {}

    try:
        resp = await _call(
            panel,
            lambda api, token: api.bulk_set_owner(BulkUsersSetOwner(ids=ids, admin_username=target), token=token),
        )
        moved = {by_username[name] for name in (getattr(resp, "users", None) or []) if name in by_username}
    except Exception as exc:
        log.warning("admin transfer: bulk_set_owner chunk failed, falling back: %s", format_exception_message(exc))
        moved = set()

    for user_id in ids:
        if user_id in moved:
            outcome[user_id] = None
            continue
        try:
            await _call(panel, lambda api, token, uid=user_id: api.set_owner_by_id(uid, target, token=token))
            outcome[user_id] = None
        except HTTPStatusError as exc:
            body = (exc.response.text or "").strip()[:200]
            outcome[user_id] = (
                f"HTTP {exc.response.status_code}: {body}" if body else f"HTTP {exc.response.status_code}"
            )
        except Exception as exc:
            outcome[user_id] = format_exception_message(exc)[:200]
    return outcome


async def _new_service_code(taken: set[int]) -> int:
    for _ in range(50):
        code = random.randint(10000, 9999999)
        if code in taken:
            continue
        found, _ = await ServiceCRUD().get_service(code)
        if not found:
            taken.add(code)
            return code
    raise RuntimeError("Could not allocate a unique service code.")


async def _create_service(panel, job: TransferJob, user: Any, taken: set[int]) -> tuple[int | None, str | None]:
    try:
        code = await _new_service_code(taken)
    except RuntimeError as exc:
        return None, str(exc)
    data_limit = int(getattr(user, "data_limit", 0) or 0)
    ok, msg = await ServiceCRUD().create_service(
        code=code,
        username=str(user.username),
        enable=True,
        in_panel=int(panel.code),
        panel_userid=int(user.id),
        id=job.telegram_id,
        package_size=data_limit or None,
        createtime=_timestamp(getattr(user, "created_at", None)) or int(time.time()),
        expiration_time=_timestamp(getattr(user, "expire", None)),
        data_limit_reset_strategy=_reset_strategy(user),
        ip_limit=0,
        is_test=False,
    )
    if not ok:
        return None, str(msg)[:200]
    return code, None


async def _execute(panel, job: TransferJob) -> None:
    users = await fetch_admin_users(panel, job.source_admin)
    active = [user for user in users if _status(user) == ACTIVE_STATUS]
    job.skipped_inactive = len(users) - len(active)
    job.total = len(active)

    job.phase = "check"
    existing = await _existing_services(job.panel_code, [str(user.username) for user in active])
    to_move: list[Any] = []
    for user in active:
        row = existing.get(str(user.username))
        if row is not None and int(row.id or 0) != job.telegram_id:
            job.rows.append(
                TransferRow(
                    username=str(user.username),
                    panel_user_id=int(user.id),
                    result="conflict",
                    reason=f"already linked to {int(row.id or 0)} in the bot",
                    service_code=int(row.code),
                )
            )
            job.processed += 1
            continue
        to_move.append(user)

    job.phase = "transfer"
    taken_codes: set[int] = set()
    for start in range(0, len(to_move), _SET_OWNER_CHUNK):
        chunk = to_move[start : start + _SET_OWNER_CHUNK]
        outcome = await _set_owner_chunk(panel, chunk, job.target_admin)
        for user in chunk:
            username = str(user.username)
            error = outcome.get(int(user.id), "no response")
            if error is not None:
                job.rows.append(TransferRow(username, int(user.id), "failed", error))
            elif (row := existing.get(username)) is not None:
                job.rows.append(TransferRow(username, int(user.id), "moved_linked", service_code=int(row.code)))
            else:
                code, db_error = await _create_service(panel, job, user, taken_codes)
                if code is None:
                    job.rows.append(TransferRow(username, int(user.id), "moved_no_record", db_error))
                else:
                    job.rows.append(TransferRow(username, int(user.id), "moved", service_code=code))
            job.processed += 1

    job.phase = "verify"
    try:
        remaining = await fetch_admin_users(panel, job.source_admin)
        job.remaining_active_on_source = sum(1 for user in remaining if _status(user) == ACTIVE_STATUS)
    except Exception as exc:
        log.warning("admin transfer: verification fetch failed: %s", format_exception_message(exc))
    job.phase = "done"


def job_csv(job: TransferJob) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["username", "panel_user_id", "result", "service_code", "reason"])
    for row in job.rows:
        writer.writerow([row.username, row.panel_user_id, row.result, row.service_code or "", row.reason or ""])
    return buffer.getvalue()


def _summary_lines(job: TransferJob) -> list[str]:
    counts = job.counts()
    moved = counts.get("moved", 0) + counts.get("moved_linked", 0) + counts.get("moved_no_record", 0)
    lines = [
        "<b>🔀 انتقال یوزرهای ادمین پنل به ربات</b>",
        "",
        f"👮 <b>انجام‌دهنده:</b> <code>{job.actor_id}</code>",
        f"👤 <b>کاربر مقصد:</b> <code>{job.telegram_id}</code>",
        f"📛 <b>پنل:</b> {job.panel_name} (<code>{job.panel_code}</code>)",
        f"📤 <b>ادمین مبدأ:</b> <code>{job.source_admin}</code>",
        f"📥 <b>ادمین مقصد:</b> <code>{job.target_admin}</code>",
        "",
        f"🟢 <b>یوزر اکتیو:</b> {job.total}",
        f"⏭ <b>غیراکتیو (منتقل نشد):</b> {job.skipped_inactive}",
        f"✅ <b>منتقل شد:</b> {moved}",
        f"🆕 <b>سرویس جدید در ربات:</b> {counts.get('moved', 0)}",
        f"🔗 <b>از قبل در ربات بود:</b> {counts.get('moved_linked', 0)}",
        f"⚠️ <b>منتقل شد ولی ثبت در ربات ناموفق:</b> {counts.get('moved_no_record', 0)}",
        f"❌ <b>ناموفق:</b> {counts.get('failed', 0)}",
        f"🚫 <b>تداخل (متعلق به کاربر دیگر):</b> {counts.get('conflict', 0)}",
    ]
    if job.remaining_active_on_source is not None:
        lines.append(f"🔎 <b>اکتیو باقی‌مانده روی مبدأ:</b> {job.remaining_active_on_source}")
    if job.error:
        lines.append(f"🛑 <b>خطا:</b> {job.error}")
    return lines


async def _report(job: TransferJob) -> None:
    try:
        file = io.BytesIO(job_csv(job).encode("utf-8-sig"))
        file.name = f"admin_transfer_{job.panel_code}_{job.source_admin}_{job.started_at}.csv"
        await send_log_message(LogType.OTHER, file=file, caption="\n".join(_summary_lines(job)), parse_mode="html")
    except Exception as exc:
        log.error("admin transfer: log report failed job=%s: %s", job.id, exc)

    if not job.notify:
        return
    counts = job.counts()
    moved = counts.get("moved", 0) + counts.get("moved_linked", 0)
    if moved <= 0:
        return
    try:
        await Kenzo.send_message(
            job.telegram_id,
            f"**✅ {moved} سرویس از پنل {job.panel_name} به حساب ربات شما منتقل شد.**\n\n"
            "از این پس می‌توانید تمدید و مدیریت این سرویس‌ها را از بخش «سرویس‌های من» انجام دهید.",
            parse_mode="markdown",
        )
    except Exception as exc:
        log.warning("admin transfer: user notify failed tg=%s: %s", job.telegram_id, exc)
