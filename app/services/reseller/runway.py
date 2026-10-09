"""How long a reseller's wallet lasts at the current pay-as-you-go spending rate."""

from __future__ import annotations

import time
from dataclasses import dataclass

from app.db.crud.reseller_billing_snapshots import ResellerBillingSnapshotCRUD
from app.db.crud.reseller_plans import ResellerPlanManager
from app.services.billing.reseller_pricing import resolve_live_unit_price

USAGE_WINDOW_SECONDS = 24 * 3600
BURNING_MODES = ("hourly", "usage")


@dataclass
class Runway:
    balance: int
    burn_per_hour: float
    hours_left: float | None


def burning_accounts(accounts) -> list:
    """Accounts that are charged right now: active hourly/usage ones."""
    return [a for a in accounts if a.status == "active" and a.pricing_mode in BURNING_MODES]


async def burn_rates(accounts) -> dict[int, float]:
    """Per-account spend per hour: hourly plans burn their rate, usage plans their last-24h average."""
    active = burning_accounts(accounts)
    rates: dict[int, float] = {}
    plans: dict[int, object] = {}
    for account in active:
        if account.pricing_mode != "hourly":
            continue
        if account.plan_id and account.plan_id not in plans:
            plans[account.plan_id] = await ResellerPlanManager().get_plan(account.plan_id)
        rates[int(account.code)] = resolve_live_unit_price(account, plans.get(account.plan_id))

    usage_codes = [int(a.code) for a in active if a.pricing_mode == "usage"]
    if usage_codes:
        totals = await ResellerBillingSnapshotCRUD().sum_billed_since(
            usage_codes, int(time.time()) - USAGE_WINDOW_SECONDS
        )
        for code in usage_codes:
            rates[code] = totals.get(code, 0) / 24
    return rates


def runway_from_burn(balance: int, burn: float) -> Runway:
    hours_left = max(0.0, balance / burn) if burn > 0 else None
    return Runway(balance=int(balance), burn_per_hour=burn, hours_left=hours_left)


async def estimate_runway(balance: int, accounts) -> Runway:
    """Runway of one user's wallet across all of their accounts."""
    rates = await burn_rates(accounts)
    return runway_from_burn(balance, sum(rates.values()))


async def estimate_runways(accounts, balances: dict[int, int]) -> dict[int, Runway]:
    """Runway per user for many users at once; plans and usage totals are loaded once for all."""
    rates = await burn_rates(accounts)
    burn_by_user: dict[int, float] = {}
    for account in burning_accounts(accounts):
        burn_by_user[account.telegram_id] = burn_by_user.get(account.telegram_id, 0.0) + rates.get(
            int(account.code), 0.0
        )
    return {
        telegram_id: runway_from_burn(int(balances.get(telegram_id, 0)), burn)
        for telegram_id, burn in burn_by_user.items()
    }


def format_runway(hours_left: float | None) -> str:
    if hours_left is None:
        return "—"
    if hours_left < 1:
        return f"{max(1, round(hours_left * 60))} دقیقه"
    if hours_left < 48:
        return f"{round(hours_left)} ساعت"
    return f"{round(hours_left / 24)} روز"
