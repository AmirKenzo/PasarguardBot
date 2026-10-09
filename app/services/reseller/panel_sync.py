"""Push admin-panel (web) edits of a reseller account to its Pasarguard panel admin.

The web panel used to write ``status`` / ``max_users`` / deletes straight to the DB, leaving the
real panel admin enabled, disabled or alive regardless of what the bot believed.
"""

from __future__ import annotations

from pasarguard import AdminModify, RoleLimits

from app.db.crud.panels import PanelsManager
from app.db.crud.reseller_accounts import ResellerAccountCRUD
from app.db.crud.reseller_billing_snapshots import ResellerBillingSnapshotCRUD
from app.logger import get_logger
from app.services.panels.admins import (
    activate_reseller_admin,
    get_reseller_admin,
    modify_reseller_admin,
    purge_reseller_admin,
    suspend_reseller_admin,
)

log = get_logger(__name__)


async def sync_reseller_status(account, new_status: str) -> tuple[bool, str | None]:
    """Enable/disable the panel admin to match ``new_status``. Returns (ok, error)."""
    if new_status == account.status:
        return True, None
    panel = await PanelsManager().get_panel_by_code(code=account.panel_code)
    if not panel:
        return False, "پنل این نمایندگی پیدا نشد."
    try:
        if new_status == "active":
            await activate_reseller_admin(panel, account.panel_admin_id)
        else:
            await suspend_reseller_admin(panel, account.panel_admin_id)
    except Exception as exc:
        log.error("web status sync failed code=%s status=%s: %s", account.code, new_status, exc)
        return False, "اعمال وضعیت روی پنل ناموفق بود."
    if new_status == "active":
        await ResellerAccountCRUD().reset_billing_clock(account.code)
    return True, None


async def sync_reseller_max_users(account, max_users: int) -> tuple[bool, str | None]:
    """Write the user limit into the panel admin's permission overrides. 0 removes the limit."""
    if int(account.max_users or 0) == int(max_users or 0):
        return True, None
    panel = await PanelsManager().get_panel_by_code(code=account.panel_code)
    if not panel:
        return False, "پنل این نمایندگی پیدا نشد."
    limit = int(max_users) if max_users and max_users > 0 else None
    try:
        current = await get_reseller_admin(panel, account.panel_admin_id)
        if not current:
            return False, "ادمین این نمایندگی در پنل پیدا نشد."
        overrides = current.permission_overrides
        if overrides is not None:
            overrides = overrides.model_copy(update={"max_users": limit})
        else:
            overrides = RoleLimits(max_users=limit)
        await modify_reseller_admin(panel, account.panel_admin_id, AdminModify(permission_overrides=overrides))
    except Exception as exc:
        log.error("web max_users sync failed code=%s: %s", account.code, exc)
        return False, "اعمال سقف کاربر روی پنل ناموفق بود."
    return True, None


async def purge_reseller_from_panel(account) -> tuple[int, bool]:
    """Delete the panel admin with its users and the billing history. Returns (deleted_users, admin_removed)."""
    deleted_users, admin_removed = 0, False
    panel = await PanelsManager().get_panel_by_code(code=account.panel_code)
    if panel:
        deleted_users, admin_removed = await purge_reseller_admin(panel, account)
    await ResellerBillingSnapshotCRUD().delete_snapshots_for_account(account.code)
    return deleted_users, admin_removed
