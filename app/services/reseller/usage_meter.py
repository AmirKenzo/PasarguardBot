"""Unbilled traffic of a usage-billed reseller: what the panel counted since the last charge.

The baseline is ``ResellerAccount.billed_traffic``, moved only by the same transaction that debits
the wallet. The ledger is history and plays no part in what gets charged.
Shared by the billing job and by user actions (resume) so both price pending usage the same way.
"""

from __future__ import annotations

from app.services.billing.reseller_pricing import resolve_live_unit_price
from app.services.panels.admins import get_reseller_admin
from app.utils.formatting.conversions import gigabytes_to_bytes


def usage_delta(used_traffic: int, baseline: int | None) -> int:
    """Bytes consumed since the last charge.

    A panel-side usage reset makes ``used_traffic`` drop below the baseline; in that case
    everything used since the reset is new, instead of waiting until it passes the old value.
    """
    last_used = int(baseline or 0)
    if used_traffic < last_used:
        return max(0, used_traffic)
    return used_traffic - last_used


def usage_charge(delta_bytes: int, rate: float) -> int:
    return round(delta_bytes / gigabytes_to_bytes(1) * rate)


async def pending_usage_charge(account, panel, plan) -> int | None:
    """Price of the traffic not billed yet; None when the panel admin can't be read."""
    admin = await get_reseller_admin(panel, account.panel_admin_id)
    if not admin:
        return None
    delta = usage_delta(int(getattr(admin, "used_traffic", 0) or 0), account.billed_traffic)
    return usage_charge(delta, resolve_live_unit_price(account, plan))
