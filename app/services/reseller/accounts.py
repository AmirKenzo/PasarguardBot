"""Reseller account operations shared by the bot, the user web app and the admin panel.

Nothing here talks to Telegram: every function returns data or ``(ok, message)`` so each
front end renders its own UI on top of the same rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.db.crud.panels import PanelsManager
from app.db.crud.reseller_accounts import ResellerAccountCRUD
from app.db.crud.reseller_billing_snapshots import ResellerBillingSnapshotCRUD
from app.db.crud.reseller_plans import ResellerPlanManager
from app.db.crud.user import UserCRUD
from app.jobs.reseller.billing import GRACE_DELETE_SECONDS
from app.logger import get_logger
from app.services.billing.reseller_pricing import resolve_live_unit_price
from app.services.panels.admins import (
    activate_reseller_admin,
    get_reseller_admin,
    reset_reseller_admin_password,
    suspend_reseller_admin,
)
from app.services.panels.settings import (
    get_panel_login_url,
    panel_reseller_button_enabled,
    panel_reseller_capacity_enabled,
)
from app.services.reseller.logging import send_reseller_log
from app.services.reseller.panel_sync import purge_reseller_from_panel
from app.services.reseller.usage_cap import USAGE_CAPPED_STATUS
from app.utils.formatting.dates import Time_Date
from app.utils.security.crypto import decrypt_data, encrypt_data

log = get_logger(__name__)

ADMIN_LOCKED_STATUS = "admin_paused"
PAYG_MODES = ("hourly", "usage")

# Actions a reseller may run on one account; front ends show a control per action.
ACTION_CREDENTIALS = "credentials"
ACTION_CHANGE_PASSWORD = "change_password"
ACTION_PAUSE = "pause"
ACTION_RESUME = "resume"
ACTION_RENEW = "renew"
ACTION_USAGE_REPORT = "usage_report"
ACTION_USAGE_CAP = "usage_cap"
ACTION_BUY_CAPACITY = "buy_user_capacity"
ACTION_DELETE = "delete"


def is_admin_locked(account) -> bool:
    return account.status == ADMIN_LOCKED_STATUS


def account_actions(account, panel) -> frozenset[str]:
    """Actions allowed for ``account`` given its status, plan and the panel's reseller button toggles."""

    def enabled(key: str) -> bool:
        return panel_reseller_button_enabled(panel, key) if panel else True

    actions: set[str] = set()
    if not is_admin_locked(account):
        if enabled("credentials"):
            actions.add(ACTION_CREDENTIALS)
        if enabled("change_password"):
            actions.add(ACTION_CHANGE_PASSWORD)
        if enabled("toggle_status"):
            if account.status == "paused":
                actions.add(ACTION_RESUME)
            elif account.status in ("active", "suspended"):
                actions.add(ACTION_PAUSE)
        if account.pricing_mode == "fixed":
            actions.add(ACTION_RENEW)
        if account.pricing_mode == "usage" and enabled("usage_report"):
            actions.add(ACTION_USAGE_REPORT)
        if account.pricing_mode == "usage" and enabled("usage_cap"):
            actions.add(ACTION_USAGE_CAP)
        if panel and panel_reseller_capacity_enabled(panel) and enabled("buy_user_capacity"):
            actions.add(ACTION_BUY_CAPACITY)
    if enabled("delete"):
        actions.add(ACTION_DELETE)
    return frozenset(actions)


async def get_owned_account(code: Any, telegram_id: int):
    """Return the account only when it belongs to ``telegram_id``."""
    ok, account = await ResellerAccountCRUD().get_account(code)
    if not ok or account.telegram_id != telegram_id:
        return None
    return account


@dataclass
class AccountLiveInfo:
    """Account data merged with the live panel admin, wallet and billing totals."""

    panel: Any
    plan: Any
    panel_name: str
    login_url: str
    used_traffic: int
    data_limit: int
    total_users: int
    admin_status: str
    live_rate: float
    balance: int | None
    billed_total: int | None
    grace_days_left: int | None


async def load_account_live_info(account) -> AccountLiveInfo:
    panel = await PanelsManager().get_panel_by_code(code=account.panel_code)
    plan = await ResellerPlanManager().get_plan(account.plan_id) if account.plan_id else None
    admin = await get_reseller_admin(panel, account.panel_admin_id) if panel else None

    used = int(getattr(admin, "used_traffic", 0) or 0) if admin else 0
    data_limit = (
        int(getattr(admin, "data_limit", 0) or account.data_limit or 0) if admin else int(account.data_limit or 0)
    )

    grace_days_left = None
    if account.expiration_time and account.status == "expired":
        grace_left = max(0, account.expiration_time + GRACE_DELETE_SECONDS - Time_Date()["stamp"])
        grace_days_left = max(1, grace_left // 86400) if grace_left else 0

    balance = billed_total = None
    if account.pricing_mode in PAYG_MODES:
        user = await UserCRUD().read_user(account.telegram_id)
        balance = user.amount if user else 0
        state = ResellerAccountCRUD.load_billing_state(account.billing_state)
        _, snapshot_total = await ResellerBillingSnapshotCRUD().get_usage_totals(account.code)
        billed_total = max(int(state.get("total_billed") or 0), snapshot_total)

    return AccountLiveInfo(
        panel=panel,
        plan=plan,
        panel_name=panel.name if panel else str(account.panel_code),
        login_url=get_panel_login_url(panel) if panel else "—",
        used_traffic=used,
        data_limit=data_limit,
        total_users=int(getattr(admin, "total_users", 0) or 0) if admin else 0,
        admin_status=str(getattr(admin, "status", None) or account.status),
        live_rate=resolve_live_unit_price(account, plan),
        balance=balance,
        billed_total=billed_total,
        grace_days_left=grace_days_left,
    )


def reveal_password(account) -> str:
    return decrypt_data(account.password_encrypted)


async def reset_password(account, *, actor_id: int | None = None) -> tuple[bool, str, str | None]:
    """Generate a new panel password. Returns (ok, message, new_password)."""
    panel = await PanelsManager().get_panel_by_code(code=account.panel_code)
    if not panel:
        return False, "پنل یافت نشد.", None
    try:
        new_password = await reset_reseller_admin_password(panel, account.panel_admin_id, account.username)
    except Exception as exc:
        log.error("password reset failed code=%s: %s", account.code, exc)
        return False, "خطا در تغییر رمز.", None
    await ResellerAccountCRUD().update_account(account.code, password_encrypted=encrypt_data(new_password))
    await send_reseller_log("🔑 تغییر رمز نمایندگی", account=account, actor_id=actor_id)
    return True, "✅ رمز جدید اعمال شد.", new_password


async def _resume_balance_error(account, *, for_admin: bool) -> str | None:
    """Wallet check before re-enabling a pay-as-you-go account; None when it may resume."""
    if account.pricing_mode not in PAYG_MODES:
        return None
    user = await UserCRUD().read_user(account.telegram_id)
    if not user:
        return None
    if account.pricing_mode == "usage" and user.amount < 1:
        return (
            "موجودی کیف پول کاربر برای فعال‌سازی کافی نیست."
            if for_admin
            else "برای فعال‌سازی مجدد موجودی کیف پول کافی نیست."
        )
    if account.pricing_mode == "hourly":
        plan = await ResellerPlanManager().get_plan(account.plan_id) if account.plan_id else None
        rate = int(resolve_live_unit_price(account, plan))
        if user.amount < max(1, rate // 60):
            return (
                "موجودی کاربر برای ادامه پلن ساعتی کافی نیست."
                if for_admin
                else "موجودی برای ادامه پلن ساعتی کافی نیست."
            )
    return None


async def pause_account(account) -> tuple[bool, str]:
    if is_admin_locked(account):
        return False, "این نمایندگی توسط ادمین غیرفعال شده است."
    if account.status == "paused":
        return True, "پنل از قبل غیرفعال است."
    if account.status == "expired":
        return False, "نمایندگی منقضی شده است."
    if account.status == USAGE_CAPPED_STATUS:
        return False, "پنل به‌خاطر سقف مصرف غیرفعال است. ابتدا سقف را تغییر دهید."

    panel = await PanelsManager().get_panel_by_code(code=account.panel_code)
    if not panel:
        return False, "پنل یافت نشد."
    try:
        await suspend_reseller_admin(panel, account.panel_admin_id)
    except Exception as exc:
        log.error("pause reseller failed code=%s: %s", account.code, exc)
        return False, "خطا در غیرفعال‌سازی پنل."

    await ResellerAccountCRUD().update_account(account.code, status="paused")
    await send_reseller_log("⏸ غیرفعال‌سازی نمایندگی توسط کاربر", account=account, actor_id=account.telegram_id)
    return True, "پنل غیرفعال شد. تا زمان فعال‌سازی مجدد، موجودی کسر نمی‌شود."


async def pause_account_by_admin(account, *, actor_id: int | None = None) -> tuple[bool, str]:
    if is_admin_locked(account):
        return True, "پنل از قبل توسط ادمین غیرفعال است."
    if account.status == "expired":
        return False, "نمایندگی منقضی شده است."

    panel = await PanelsManager().get_panel_by_code(code=account.panel_code)
    if not panel:
        return False, "پنل یافت نشد."
    try:
        await suspend_reseller_admin(panel, account.panel_admin_id)
    except Exception as exc:
        log.error("admin pause reseller failed code=%s: %s", account.code, exc)
        return False, "خطا در غیرفعال‌سازی پنل."

    await ResellerAccountCRUD().update_account(account.code, status=ADMIN_LOCKED_STATUS)
    await send_reseller_log(
        "⛔️ غیرفعال‌سازی نمایندگی توسط ادمین", account=account, actor_id=actor_id, actor_role="ادمین"
    )
    return True, "نمایندگی توسط ادمین غیرفعال شد."


async def resume_account(account) -> tuple[bool, str]:
    if is_admin_locked(account):
        return False, "فعال‌سازی این نمایندگی فقط توسط ادمین امکان‌پذیر است."
    if account.status != "paused":
        return False, "این نمایندگی در حالت غیرفعال نیست."

    panel = await PanelsManager().get_panel_by_code(code=account.panel_code)
    if not panel:
        return False, "پنل یافت نشد."
    error = await _resume_balance_error(account, for_admin=False)
    if error:
        return False, error
    try:
        await activate_reseller_admin(panel, account.panel_admin_id)
    except Exception as exc:
        log.error("resume reseller failed code=%s: %s", account.code, exc)
        return False, "خطا در فعال‌سازی پنل."

    await ResellerAccountCRUD().reset_billing_clock(account.code, status="active")
    await send_reseller_log("▶️ فعال‌سازی نمایندگی توسط کاربر", account=account, actor_id=account.telegram_id)
    return True, "پنل دوباره فعال شد."


async def resume_account_by_admin(account, *, actor_id: int | None = None) -> tuple[bool, str]:
    if account.status not in ("paused", ADMIN_LOCKED_STATUS):
        return False, "این نمایندگی در حالت غیرفعال نیست."

    panel = await PanelsManager().get_panel_by_code(code=account.panel_code)
    if not panel:
        return False, "پنل یافت نشد."
    if account.status == "paused":
        error = await _resume_balance_error(account, for_admin=True)
        if error:
            return False, error
    try:
        await activate_reseller_admin(panel, account.panel_admin_id)
    except Exception as exc:
        log.error("admin resume reseller failed code=%s: %s", account.code, exc)
        return False, "خطا در فعال‌سازی پنل."

    await ResellerAccountCRUD().reset_billing_clock(account.code, status="active")
    await send_reseller_log("▶️ فعال‌سازی نمایندگی توسط ادمین", account=account, actor_id=actor_id, actor_role="ادمین")
    return True, "نمایندگی توسط ادمین فعال شد."


async def delete_account(account, *, actor_id: int | None = None, actor_role: str = "کاربر") -> tuple[bool, str]:
    deleted_users, admin_removed = await purge_reseller_from_panel(account)
    await ResellerAccountCRUD().delete_account(account.code)
    await send_reseller_log(
        "🗑 حذف نمایندگی",
        account=account,
        actor_id=actor_id or account.telegram_id,
        actor_role=actor_role,
        extra_lines=[
            f"👥 <b>یوزر حذف‌شده:</b> <code>{deleted_users}</code>",
            f"🧹 <b>ادمین از پنل:</b> <code>{'بله' if admin_removed else 'خیر'}</code>",
        ],
    )
    panel_missing = not await PanelsManager().get_panel_by_code(code=account.panel_code)
    if not admin_removed and not panel_missing:
        return False, "حذف ادمین از پنل ناموفق بود. با پشتیبانی تماس بگیرید."
    return True, f"نمایندگی `{account.username}` و {deleted_users} یوزر وابسته حذف شدند."
