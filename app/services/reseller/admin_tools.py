"""Admin tools to correct one reseller account: volume, plan, panel sync and unbilled usage.

Every tool writes the panel first and the DB only after the panel accepted, so the two never
disagree, and records an event with who did it. Used by the admin panel and the bot's admin menu.
"""

from __future__ import annotations

from pasarguard import AdminModify, RoleLimits

from app.db.crud.panels import PanelsManager
from app.db.crud.reseller_accounts import ResellerAccountCRUD
from app.db.crud.reseller_plans import ResellerPlanManager
from app.logger import get_logger
from app.services.panels.admins import (
    activate_reseller_admin,
    get_reseller_admin,
    modify_reseller_admin,
    suspend_reseller_admin,
)
from app.services.reseller.logging import (
    EVENT_DATA_LIMIT,
    EVENT_PANEL_SYNC,
    EVENT_PLAN_CHANGE,
    EVENT_USAGE_FORGIVEN,
    send_reseller_log,
)
from app.services.reseller.plan_rules import USAGE, rule_for
from app.utils.formatting.conversions import gigabytes_to_bytes
from app.utils.formatting.traffic import format_size

log = get_logger(__name__)

ADMIN_ROLE = "ادمین"
# Statuses where the panel admin must be switched off.
_DISABLED_STATUSES = ("paused", "suspended", "expired", "admin_paused", "usage_capped")


async def _panel(account):
    return await PanelsManager().get_panel_by_code(code=account.panel_code)


def effective_max_users(plan, extra_users: int | None) -> int:
    """The plan's user limit plus bought slots; 0 (unlimited) when the plan has no limit."""
    plan_max = int(plan.max_users or 0) if plan else 0
    return plan_max + int(extra_users or 0) if plan_max > 0 else 0


async def _write_max_users(panel, account, limit: int) -> None:
    current = await get_reseller_admin(panel, account.panel_admin_id)
    if not current:
        raise RuntimeError("admin not found on panel")
    value = limit if limit > 0 else None
    overrides = current.permission_overrides
    overrides = (
        overrides.model_copy(update={"max_users": value}) if overrides is not None else RoleLimits(max_users=value)
    )
    await modify_reseller_admin(panel, account.panel_admin_id, AdminModify(permission_overrides=overrides))


async def set_data_limit_by_admin(
    account, *, set_gb: float | None = None, add_gb: float | None = None, actor_id: int | None = None
) -> tuple[bool, str]:
    """Set the volume to ``set_gb`` or add ``add_gb`` to it, for free."""
    if rule_for(account.pricing_mode).volume == "none":
        return False, "حجم این نوع پلن همیشه نامحدود است."
    before = int(account.data_limit or 0)
    if set_gb is not None:
        if set_gb <= 0:
            return False, "حجم باید بیشتر از صفر باشد."
        after = int(gigabytes_to_bytes(set_gb))
    elif add_gb is not None:
        if add_gb <= 0:
            return False, "حجم باید بیشتر از صفر باشد."
        if before <= 0:
            return False, "حجم فعلی نامحدود است؛ حجم دقیق را تعیین کنید."
        after = before + int(gigabytes_to_bytes(add_gb))
    else:
        return False, "مقداری وارد نشده است."

    panel = await _panel(account)
    if not panel:
        return False, "پنل یافت نشد."
    try:
        await modify_reseller_admin(panel, account.panel_admin_id, AdminModify(data_limit=after))
    except Exception as exc:
        log.error("admin data limit failed code=%s: %s", account.code, exc)
        return False, "اعمال حجم روی پنل ناموفق بود."
    await ResellerAccountCRUD().update_account(account.code, data_limit=after)
    await send_reseller_log(
        "📦 تغییر حجم نمایندگی توسط ادمین",
        account=account,
        actor_id=actor_id,
        actor_role=ADMIN_ROLE,
        extra_lines=[f"📉 <b>قبل:</b> {format_size(before)}", f"📈 <b>بعد:</b> {format_size(after)}"],
        event=EVENT_DATA_LIMIT,
        data={"before": before, "after": after},
    )
    return True, f"حجم نمایندگی {format_size(after)} شد."


async def change_plan_by_admin(account, *, plan_id: int, actor_id: int | None = None) -> tuple[bool, str]:
    """Move the account to another plan of the same panel and type, without charging.

    The panel role and the user limit follow the new plan; bought user slots are kept. Volume and
    expiry stay as they are: the next renewal adds the new plan's volume and days.
    """
    if int(plan_id) == int(account.plan_id or 0):
        return True, "نمایندگی از قبل روی همین پلن است."
    plan = await ResellerPlanManager().get_plan(plan_id)
    if not plan:
        return False, "پلن یافت نشد."
    if int(plan.panel_code) != int(account.panel_code):
        return False, "پلن جدید باید متعلق به همان پنل باشد."
    if plan.pricing_mode != account.pricing_mode:
        return False, "پلن جدید باید هم‌نوع پلن فعلی باشد."

    panel = await _panel(account)
    if not panel:
        return False, "پنل یافت نشد."
    limit = effective_max_users(plan, account.extra_users)
    try:
        await modify_reseller_admin(panel, account.panel_admin_id, AdminModify(role_id=int(plan.role_id)))
        await _write_max_users(panel, account, limit)
    except Exception as exc:
        log.error("admin plan change failed code=%s: %s", account.code, exc)
        return False, "اعمال پلن جدید روی پنل ناموفق بود."
    old_plan_id = account.plan_id
    await ResellerAccountCRUD().update_account(account.code, plan_id=plan.id, max_users=limit or None)
    await send_reseller_log(
        "🔁 تغییر پلن نمایندگی توسط ادمین",
        account=account,
        actor_id=actor_id,
        actor_role=ADMIN_ROLE,
        extra_lines=[f"📋 <b>پلن:</b> <code>{old_plan_id}</code> ← <code>{plan.id}</code>"],
        event=EVENT_PLAN_CHANGE,
        data={"plan_before": old_plan_id, "plan_after": plan.id, "max_users": limit},
    )
    return True, "پلن نمایندگی تغییر کرد."


async def resync_with_panel(account, *, actor_id: int | None = None) -> tuple[bool, str]:
    """Write what the bot stores (status, volume, user limit, role) onto the panel admin again."""
    panel = await _panel(account)
    if not panel:
        return False, "پنل یافت نشد."
    plan = await ResellerPlanManager().get_plan(account.plan_id) if account.plan_id else None
    changes: dict = {}
    if plan:
        changes["role_id"] = int(plan.role_id)
    # 0 means unlimited in the bot; the panel keeps its own value then.
    if int(account.data_limit or 0) > 0:
        changes["data_limit"] = int(account.data_limit)
    try:
        if changes:
            await modify_reseller_admin(panel, account.panel_admin_id, AdminModify(**changes))
        await _write_max_users(panel, account, int(account.max_users or 0))
        if account.status in _DISABLED_STATUSES:
            await suspend_reseller_admin(panel, account.panel_admin_id)
        else:
            await activate_reseller_admin(panel, account.panel_admin_id)
    except Exception as exc:
        log.error("admin panel resync failed code=%s: %s", account.code, exc)
        return False, "همگام‌سازی با پنل ناموفق بود."
    await send_reseller_log(
        "🔄 همگام‌سازی نمایندگی با پنل توسط ادمین",
        account=account,
        actor_id=actor_id,
        actor_role=ADMIN_ROLE,
        event=EVENT_PANEL_SYNC,
        data={"status": account.status, **changes, "max_users": int(account.max_users or 0)},
    )
    return True, "اطلاعات نمایندگی دوباره روی پنل نوشته شد."


async def forgive_unbilled_usage(account, *, actor_id: int | None = None) -> tuple[bool, str]:
    """Usage plans: drop the traffic used since the last charge, so it is never billed."""
    if account.pricing_mode != USAGE:
        return False, "این ابزار فقط برای پلن مصرفی است."
    panel = await _panel(account)
    if not panel:
        return False, "پنل یافت نشد."
    admin = await get_reseller_admin(panel, account.panel_admin_id)
    if not admin:
        return False, "ادمین این نمایندگی در پنل پیدا نشد."
    used = int(getattr(admin, "used_traffic", 0) or 0)
    forgiven = max(0, used - int(account.billed_traffic or 0))
    # Moving the baseline makes a billing run that read the old one skip (its charge is stale).
    await ResellerAccountCRUD().patch_billing_state(
        account.code, updates={"last_used_traffic": used}, billed_traffic=used
    )
    await send_reseller_log(
        "🎁 بخشیدن مصرف کسرنشده توسط ادمین",
        account=account,
        actor_id=actor_id,
        actor_role=ADMIN_ROLE,
        extra_lines=[f"📦 <b>حجم بخشیده‌شده:</b> {format_size(forgiven)}"],
        event=EVENT_USAGE_FORGIVEN,
        data={"forgiven_bytes": forgiven, "billed_traffic": used},
    )
    return True, f"{format_size(forgiven)} مصرف کسرنشده بخشیده شد."
