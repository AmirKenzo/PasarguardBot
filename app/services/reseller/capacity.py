"""Extra reseller user slots; the price is set per plan (``addon_user_price``)."""

from __future__ import annotations

from app.db.crud.reseller_plans import ResellerPlanManager
from app.services.reseller.addons import buy_addon
from app.services.reseller.plan_rules import ADDON_USERS, addon_price

CAPACITY_PRESETS: tuple[int, ...] = (5, 10, 20, 30, 50, 100)


def capacity_price_per_user(plan) -> int:
    """Price of one extra user slot on ``plan``; 0 when the add-on is off."""
    return addon_price(plan, ADDON_USERS)


async def increase_reseller_capacity(
    account,
    panel,
    *,
    quantity: int,
    telegram_id: int,
    source: str = "preset",
    actor_id: int | None = None,
    actor_role: str | None = None,
) -> tuple[bool, str]:
    """Buy extra user slots; kept for older callers, the work is done by ``buy_addon``.

    Caller must hold the ``ADDON_LOCK`` user lock around this call.
    """
    plan = await ResellerPlanManager().get_plan(account.plan_id) if account.plan_id else None
    ok, message, _ = await buy_addon(
        account, panel, plan, ADDON_USERS, quantity, telegram_id=telegram_id, actor_id=actor_id, source=source
    )
    return ok, message
