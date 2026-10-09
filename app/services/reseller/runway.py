"""How long a reseller's wallet lasts at the current pay-as-you-go spending rate."""

from __future__ import annotations

import time
from dataclasses import dataclass

from app.db.crud.reseller_billing_snapshots import ResellerBillingSnapshotCRUD
from app.db.crud.reseller_plans import ResellerPlanManager
from app.services.billing.reseller_pricing import resolve_live_unit_price

USAGE_WINDOW_SECONDS = 24 * 3600


@dataclass
class Runway:
    balance: int
    burn_per_hour: float
    hours_left: float | None


async def estimate_runway(balance: int, accounts) -> Runway:
    """Hourly accounts burn their plan rate; usage accounts burn their last-24h average."""
    active = [a for a in accounts if a.status == "active" and a.pricing_mode in ("hourly", "usage")]
    burn = 0.0
    plans: dict[int, object] = {}
    for account in active:
        if account.pricing_mode != "hourly":
            continue
        if account.plan_id and account.plan_id not in plans:
            plans[account.plan_id] = await ResellerPlanManager().get_plan(account.plan_id)
        burn += resolve_live_unit_price(account, plans.get(account.plan_id))

    usage_codes = [int(a.code) for a in active if a.pricing_mode == "usage"]
    if usage_codes:
        totals = await ResellerBillingSnapshotCRUD().sum_billed_since(
            usage_codes, int(time.time()) - USAGE_WINDOW_SECONDS
        )
        burn += sum(totals.values()) / 24

    hours_left = max(0.0, balance / burn) if burn > 0 else None
    return Runway(balance=int(balance), burn_per_hour=burn, hours_left=hours_left)


def format_runway(hours_left: float | None) -> str:
    if hours_left is None:
        return "—"
    if hours_left < 1:
        return f"{max(1, round(hours_left * 60))} دقیقه"
    if hours_left < 48:
        return f"{round(hours_left)} ساعت"
    return f"{round(hours_left / 24)} روز"
