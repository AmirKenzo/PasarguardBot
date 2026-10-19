"""Push admin-panel (web) edits of a reseller account to its Pasarguard panel admin.

The web panel used to write ``status`` / ``max_users`` / deletes straight to the DB, leaving the
real panel admin enabled, disabled or alive regardless of what the bot believed.
"""

from __future__ import annotations

from pasarguard import AdminModify, RoleLimits

from app.db.crud.panels import PanelsManager
from app.db.crud.reseller_billing_snapshots import ResellerBillingSnapshotCRUD
from app.logger import get_logger
from app.services.panels.admins import (
    get_reseller_admin,
    modify_reseller_admin,
    purge_reseller_admin,
)

log = get_logger(__name__)


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
    """Delete the panel admin with its users. Returns (deleted_users, safe_to_drop).

    ``safe_to_drop`` is False while the admin still exists on a reachable panel; callers must
    then keep the account row, otherwise the bot loses track of a live admin and its users.
    Billing history is removed only once the row may go.
    """
    panel = await PanelsManager().get_panel_by_code(code=account.panel_code)
    if not panel:
        await ResellerBillingSnapshotCRUD().delete_snapshots_for_account(account.code)
        return 0, True
    deleted_users, admin_removed = await purge_reseller_admin(panel, account)
    if admin_removed:
        await ResellerBillingSnapshotCRUD().delete_snapshots_for_account(account.code)
    return deleted_users, admin_removed
