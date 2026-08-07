"""Unified per-minute reseller billing (hourly + usage) with auto suspend/reactivate."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

from pasarguard import AdminModify

from app import Kenzo
from app.db.crud.panels import PanelsManager
from app.db.crud.reseller_accounts import ResellerAccountCRUD
from app.db.crud.reseller_billing_snapshots import ResellerBillingSnapshotCRUD
from app.db.crud.reseller_plans import ResellerPlanManager
from app.db.crud.settings import SettingsManager
from app.db.crud.user import UserCRUD, update_Money
from app.logger import LogTag, get_logger
from app.services.billing.reseller_pricing import resolve_live_unit_price
from app.services.panels.admins import (
    activate_reseller_admin,
    get_reseller_admin,
    get_reseller_admins_by_username,
    modify_reseller_admin,
    purge_reseller_admin,
    suspend_reseller_admin,
)
from app.services.reseller.logging import send_reseller_log, send_reseller_usage_charge_table
from app.services.reseller.usage_cap import USAGE_CAPPED_STATUS, apply_usage_cap_suspend
from app.utils.formatting.conversions import gigabytes_to_bytes
from app.utils.formatting.dates import Time_Date
from app.utils.formatting.traffic import format_size

log = get_logger(__name__)

GRACE_DELETE_SECONDS = 7 * 86400
BILLING_SNAPSHOT_RETENTION_DAYS = 90
_ADMIN_NOT_PROVIDED = object()
_last_snapshot_cleanup_at = 0


@dataclass
class _BillingRunStats:
    hourly_accounts: int = 0
    usage_accounts: int = 0
    hourly_charged: int = 0
    usage_charged: int = 0
    suspended: int = 0
    reactivated: int = 0
    expired: int = 0
    purged: int = 0
    snapshots_purged: int = 0
    errors: int = 0
    usage_charge_rows: list[dict] = field(default_factory=list)


async def _resolve_plan(account, *, plans_by_id: dict | None = None):
    if not account.plan_id:
        return None
    if plans_by_id is not None and account.plan_id in plans_by_id:
        return plans_by_id[account.plan_id]
    return await ResellerPlanManager().get_plan(account.plan_id)


async def _notify_user(telegram_id: int, text: str) -> None:
    try:
        await Kenzo.send_message(telegram_id, text, parse_mode="markdown")
    except Exception as exc:
        log.warning("reseller billing notify failed user=%s: %s", telegram_id, exc)


async def _notify_usage_cap(account, reason: str) -> None:
    cap = account.usage_cap_bytes
    cap_text = format_size(cap) if cap else "—"
    await _notify_user(
        account.telegram_id,
        f"⛔️ **نمایندگی `{account.username}` به‌خاطر سقف مصرف غیرفعال شد**\n\n"
        f"{reason}\n"
        f"🚦 سقف: `{cap_text}`\n\n"
        "برای فعال‌سازی مجدد، از دکمه محدودیت مصرف سقف را افزایش دهید یا حذف کنید.",
    )


async def _enforce_usage_cap(account, panel, used_traffic: int, *, stats: _BillingRunStats | None = None) -> bool:
    """Suspend account when manual usage cap is reached. Returns True if capped."""
    cap = account.usage_cap_bytes
    if not cap or used_traffic < cap:
        return False
    if account.status == USAGE_CAPPED_STATUS:
        return True
    ok = await apply_usage_cap_suspend(
        account,
        panel,
        reason=f"مصرف به سقف دستی ({format_size(cap)}) رسید.",
        notify=_notify_usage_cap,
    )
    if ok and stats:
        stats.suspended += 1
    return ok


async def _suspend_account(
    account, panel, *, reason: str, charge: int = 0, balance: int | None = None, stats: _BillingRunStats | None = None
) -> None:
    if account.status == "suspended":
        return
    try:
        await modify_reseller_admin(panel, account.username, AdminModify(status="disabled"))
    except Exception as exc:
        log.error("suspend reseller failed code=%s: %s", account.code, exc)
        if stats:
            stats.errors += 1
        return

    await ResellerAccountCRUD().update_account(account.code, status="suspended")
    if stats:
        stats.suspended += 1
    charge_line = f"\n💸 مبلغ مصرف جدید: `{charge:,}` تومان" if charge else ""
    balance_line = f"\n💳 موجودی فعلی: `{balance:,}` تومان" if balance is not None else ""
    await _notify_user(
        account.telegram_id,
        f"⛔️ **نمایندگی `{account.username}` تعلیق شد**\n\n{reason}{charge_line}{balance_line}\n\n"
        f"با شارژ کیف پول، حداکثر تا ۱ دقیقه بعد دوباره فعال می‌شود.",
    )
    extra = []
    if charge:
        extra.append(f"💸 <b>مبلغ مصرف جدید:</b> <code>{charge:,}</code> تومان")
    if balance is not None:
        extra.append(f"💳 <b>موجودی فعلی:</b> <code>{balance:,}</code> تومان")
    await send_reseller_log(
        "⛔️ تعلیق نمایندگی",
        account=account,
        extra_lines=[f"📌 <b>دلیل:</b> {reason}", *extra],
    )


async def _reactivate_account(account, panel, *, stats: _BillingRunStats | None = None) -> None:
    if account.status not in ("suspended", "paused"):
        return
    try:
        await activate_reseller_admin(panel, account.username)
    except Exception as exc:
        log.error("reactivate reseller failed code=%s: %s", account.code, exc)
        if stats:
            stats.errors += 1
        return

    await ResellerAccountCRUD().update_account(account.code, status="active")
    if stats:
        stats.reactivated += 1
    await _notify_user(account.telegram_id, f"✅ **نمایندگی `{account.username}` دوباره فعال شد.**")
    await send_reseller_log("✅ فعال‌سازی مجدد نمایندگی (خودکار)", account=account)


def _reactivation_balance_needed(account, *, hourly_rate: int = 0) -> int:
    """Minimum balance to auto-reactivate after top-up (not the purchase floor)."""
    if account.pricing_mode == "hourly" and hourly_rate > 0:
        return max(1, round(hourly_rate / 60))
    return 1


async def _process_hourly_account(
    account,
    settings,
    now: int,
    *,
    stats: _BillingRunStats | None = None,
    panel=None,
    plan=None,
) -> None:
    state = ResellerAccountCRUD.load_billing_state(account.billing_state)
    last_billed = int(state.get("last_billed_at") or account.createtime or now)
    elapsed_seconds = max(0, now - last_billed)
    if elapsed_seconds < 60:
        return

    if plan is None:
        plan = await _resolve_plan(account)
    hourly_rate = int(resolve_live_unit_price(account, plan))
    if hourly_rate <= 0:
        return

    elapsed_minutes = elapsed_seconds // 60
    charge = max(1, round(hourly_rate * elapsed_minutes / 60))
    user = await UserCRUD().read_user(account.telegram_id)
    balance = user.amount if user else 0
    if not user or balance < charge:
        if panel is None:
            panel = await PanelsManager().get_panel_by_code(code=account.panel_code)
        if not panel:
            return
        await _suspend_account(
            account,
            panel,
            reason="موجودی کیف پول برای ادامه پلن ساعتی کافی نیست.",
            charge=charge,
            balance=balance,
            stats=stats,
        )
        return

    await update_Money(user_id=account.telegram_id, Money=-charge)
    state["last_billed_at"] = last_billed + elapsed_minutes * 60
    await ResellerAccountCRUD().update_account(
        account.code,
        billing_state=json.dumps(state, ensure_ascii=False),
        status="active",
    )
    await send_reseller_log(
        "⏱ کسر ساعتی نمایندگی",
        account=account,
        extra_lines=[
            f"💸 <b>مبلغ:</b> <code>{charge:,}</code> تومان",
            f"⏱ <b>دقیقه:</b> <code>{elapsed_minutes}</code>",
        ],
    )
    if stats:
        stats.hourly_charged += 1


async def _process_usage_account(
    account,
    settings,
    now: int,
    *,
    stats: _BillingRunStats | None = None,
    panel=None,
    admin=_ADMIN_NOT_PROVIDED,
) -> None:
    if panel is None:
        panel = await PanelsManager().get_panel_by_code(code=account.panel_code)
        if not panel:
            return
    plan = await _resolve_plan(account)
    if admin is _ADMIN_NOT_PROVIDED:
        admin = await get_reseller_admin(panel, account.username)
    if not admin:
        return

    used_traffic = int(getattr(admin, "used_traffic", 0) or 0)
    snapshot_crud = ResellerBillingSnapshotCRUD()
    snapshot = await snapshot_crud.get_latest_snapshot(account.code)
    last_used = int(snapshot.used_traffic if snapshot else 0)
    delta_bytes = max(0, used_traffic - last_used)

    state = ResellerAccountCRUD.load_billing_state(account.billing_state)
    rate = resolve_live_unit_price(account, plan)
    user = await UserCRUD().read_user(account.telegram_id)
    balance = user.amount if user else 0
    reactivate_needed = _reactivation_balance_needed(account)

    if delta_bytes <= 0:
        if account.status == "suspended" and user and balance >= reactivate_needed:
            await _reactivate_account(account, panel, stats=stats)
            ok, account = await ResellerAccountCRUD().get_account(account.code)
            if not ok:
                return
        await _enforce_usage_cap(account, panel, used_traffic, stats=stats)
        return

    delta_gb = delta_bytes / gigabytes_to_bytes(1)
    charge = round(delta_gb * rate)
    if charge <= 0:
        await snapshot_crud.add_snapshot(account.code, used_traffic, 0, now)
        await _enforce_usage_cap(account, panel, used_traffic, stats=stats)
        return

    if not user or balance < charge:
        await _suspend_account(
            account,
            panel,
            reason="موجودی برای پرداخت مصرف جدید کافی نیست.",
            charge=charge,
            balance=balance,
            stats=stats,
        )
        return

    await update_Money(user_id=account.telegram_id, Money=-charge)
    state["last_used_traffic"] = used_traffic
    state["total_billed"] = int(state.get("total_billed") or 0) + charge
    await ResellerAccountCRUD().update_account(
        account.code,
        billing_state=json.dumps(state, ensure_ascii=False),
        status="active",
    )
    await snapshot_crud.add_snapshot(account.code, used_traffic, charge, now)
    if stats:
        stats.usage_charged += 1
        stats.usage_charge_rows.append(
            {
                "code": account.code,
                "username": account.username,
                "telegram_id": account.telegram_id,
                "panel_code": account.panel_code,
                "status": account.status,
                "max_users": account.max_users or 0,
                "usage_bytes": int(delta_bytes),
                "charge": f"{charge:,}",
            }
        )
        if len(stats.usage_charge_rows) > 150:
            stats.usage_charge_rows = stats.usage_charge_rows[-150:]

    await _enforce_usage_cap(account, panel, used_traffic, stats=stats)


def _group_accounts_by_panel(accounts) -> dict[int, list]:
    grouped: dict[int, list] = {}
    for account in accounts:
        grouped.setdefault(account.panel_code, []).append(account)
    return grouped


async def _try_reactivate_suspended(settings, *, stats: _BillingRunStats | None = None) -> None:
    accounts = await ResellerAccountCRUD().get_accounts_by_status("suspended")
    if not accounts:
        return
    snapshot_crud = ResellerBillingSnapshotCRUD()
    panels_by_code = {p.code: p for p in await PanelsManager().get_all_panels()}
    plan_ids = {account.plan_id for account in accounts if account.plan_id}
    plans_by_id: dict = {}
    for plan_id in plan_ids:
        plan = await ResellerPlanManager().get_plan(plan_id)
        if plan:
            plans_by_id[plan_id] = plan

    for account in accounts:
        if account.pricing_mode not in ("hourly", "usage"):
            continue
        user = await UserCRUD().read_user(account.telegram_id)
        if not user:
            continue

        panel = panels_by_code.get(account.panel_code)
        if not panel:
            continue
        plan = await _resolve_plan(account, plans_by_id=plans_by_id)
        hourly_rate = int(resolve_live_unit_price(account, plan))
        needed = _reactivation_balance_needed(account, hourly_rate=hourly_rate)

        # Cheap balance gate before expensive panel HTTP for usage accounts.
        if user.amount < needed:
            continue

        if account.pricing_mode == "usage":
            # Prevent suspend/reactivate flapping: for usage accounts, require enough
            # balance to cover pending usage since the last billed snapshot.
            admin = await get_reseller_admin(panel, account.username)
            if not admin:
                continue
            snapshot = await snapshot_crud.get_latest_snapshot(account.code)
            last_used = int(snapshot.used_traffic if snapshot else 0)
            used_traffic = int(getattr(admin, "used_traffic", 0) or 0)
            delta_bytes = max(0, used_traffic - last_used)
            rate = resolve_live_unit_price(account, plan)
            pending_charge = round((delta_bytes / gigabytes_to_bytes(1)) * rate)
            needed = max(needed, pending_charge if pending_charge > 0 else 1)
            if user.amount < needed:
                continue

        await _reactivate_account(account, panel, stats=stats)


async def _expire_timed_accounts(now: int, *, stats: _BillingRunStats | None = None) -> None:
    accounts = await ResellerAccountCRUD().get_accounts_to_expire(now)
    for account in accounts:
        panel = await PanelsManager().get_panel_by_code(code=account.panel_code)
        if panel:
            try:
                await suspend_reseller_admin(panel, account.username)
            except Exception as exc:
                log.error("expire reseller suspend failed code=%s: %s", account.code, exc)
        await ResellerAccountCRUD().update_account(account.code, status="expired")
        if stats:
            stats.expired += 1
        await _notify_user(
            account.telegram_id,
            f"⌛ **نمایندگی `{account.username}` منقضی شد.**\n\n"
            f"تا ۷ روز دیگر در صورت عدم تمدید، ادمین و یوزرهای آن از پنل حذف می‌شوند.",
        )
        await send_reseller_log("⌛ انقضای نمایندگی", account=account)


async def _purge_expired_accounts(now: int, *, stats: _BillingRunStats | None = None) -> None:
    grace_before = now - GRACE_DELETE_SECONDS
    accounts = await ResellerAccountCRUD().get_accounts_for_grace_deletion(grace_before)
    snapshot_crud = ResellerBillingSnapshotCRUD()
    for account in accounts:
        panel = await PanelsManager().get_panel_by_code(code=account.panel_code)
        deleted_users = 0
        admin_removed = False
        if panel:
            deleted_users, admin_removed = await purge_reseller_admin(panel, account)
        await snapshot_crud.delete_snapshots_for_account(account.code)
        await ResellerAccountCRUD().delete_account(account.code)
        if stats:
            stats.purged += 1
        await _notify_user(
            account.telegram_id,
            f"🗑 **نمایندگی `{account.username}` پس از ۷ روز مهلت، به‌طور کامل حذف شد.**",
        )
        await send_reseller_log(
            "🗑 حذف خودکار نمایندگی منقضی",
            account=account,
            extra_lines=[
                f"👥 <b>یوزر حذف‌شده:</b> <code>{deleted_users}</code>",
                f"🧹 <b>ادمین از پنل:</b> <code>{'بله' if admin_removed else 'خیر'}</code>",
            ],
        )


async def _purge_old_billing_snapshots(now: int, *, stats: _BillingRunStats | None = None) -> None:
    global _last_snapshot_cleanup_at
    if now - _last_snapshot_cleanup_at < 3600:
        return
    cutoff = now - BILLING_SNAPSHOT_RETENTION_DAYS * 86400
    removed = await ResellerBillingSnapshotCRUD().delete_snapshots_before(cutoff)
    _last_snapshot_cleanup_at = now
    if removed:
        if stats:
            stats.snapshots_purged = removed
        log.info("Purged %s reseller billing snapshots older than %s days", removed, BILLING_SNAPSHOT_RETENTION_DAYS)


async def run_reseller_billing() -> None:
    start_time = time.time()
    log.debug("%s reseller_billing started", LogTag.JOB)

    settings = await SettingsManager().get_settings()
    if not settings or not settings.reseller_sale_mode:
        log.debug("%s reseller_billing skipped (reseller_sale_mode off)", LogTag.JOB)
        return

    stats = _BillingRunStats()
    now = Time_Date()["stamp"]
    await _purge_old_billing_snapshots(now, stats=stats)
    await _expire_timed_accounts(now, stats=stats)
    await _purge_expired_accounts(now, stats=stats)
    await _try_reactivate_suspended(settings, stats=stats)

    hourly_accounts = await ResellerAccountCRUD().get_billable_accounts(("hourly",))
    stats.hourly_accounts = len(hourly_accounts)
    hourly_panels = {p.code: p for p in await PanelsManager().get_all_panels()}
    hourly_plan_ids = {account.plan_id for account in hourly_accounts if account.plan_id}
    hourly_plans: dict = {}
    for plan_id in hourly_plan_ids:
        plan = await ResellerPlanManager().get_plan(plan_id)
        if plan:
            hourly_plans[plan_id] = plan
    for account in hourly_accounts:
        if account.status == "suspended":
            continue
        try:
            await _process_hourly_account(
                account,
                settings,
                now,
                stats=stats,
                panel=hourly_panels.get(account.panel_code),
                plan=await _resolve_plan(account, plans_by_id=hourly_plans),
            )
        except Exception as exc:
            stats.errors += 1
            log.error("hourly billing error code=%s: %s", account.code, exc)

    usage_accounts = await ResellerAccountCRUD().get_billable_accounts(("usage",))
    stats.usage_accounts = len(usage_accounts)
    for panel_code, panel_accounts in _group_accounts_by_panel(usage_accounts).items():
        panel = await PanelsManager().get_panel_by_code(code=panel_code)
        if not panel:
            continue

        usernames = {account.username for account in panel_accounts if account.username}
        try:
            admins_by_username = await get_reseller_admins_by_username(panel, usernames)
        except Exception as exc:
            stats.errors += len(panel_accounts)
            log.error("usage billing admins fetch error panel=%s: %s", panel_code, exc)
            continue

        for account in panel_accounts:
            try:
                await _process_usage_account(
                    account,
                    settings,
                    now,
                    stats=stats,
                    panel=panel,
                    admin=admins_by_username.get(account.username),
                )
            except Exception as exc:
                stats.errors += 1
                log.error("usage billing error code=%s: %s", account.code, exc)

    elapsed = time.time() - start_time
    if stats.usage_charge_rows:
        await send_reseller_usage_charge_table(stats.usage_charge_rows)
    log.info(
        f"{LogTag.JOB} reseller_billing | duration={elapsed:.2f}s, "
        f"hourly={stats.hourly_accounts}, usage={stats.usage_accounts}, "
        f"hourly_charged={stats.hourly_charged}, usage_charged={stats.usage_charged}, "
        f"suspended={stats.suspended}, reactivated={stats.reactivated}, "
        f"expired={stats.expired}, purged={stats.purged}, "
        f"snapshots_purged={stats.snapshots_purged}, errors={stats.errors}"
    )
