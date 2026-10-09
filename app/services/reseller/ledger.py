"""Explain each reseller charge: what was used, at which rate, over which period.

Rows written since the ledger-detail migration store this directly; older rows only kept the panel's
cumulative counter and the amount, so their usage is rebuilt from the previous row and their rate
from ``amount / usage`` (flagged ``rate_estimated``).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.db.crud.reseller_billing_snapshots import ResellerBillingSnapshotCRUD
from app.utils.formatting.conversions import gigabytes_to_bytes

GB = gigabytes_to_bytes(1)


@dataclass
class LedgerEntry:
    id: int
    account_code: int
    kind: str  # "hourly" | "usage"
    charged_at: int
    amount: int
    period_start: int | None
    used_bytes: int | None
    minutes: int | None
    unit_price: float | None
    rate_estimated: bool
    panel_counter: int
    is_debt: bool


def _usage_since(counter: int, previous) -> int:
    """Same rule as billing: a counter below the previous reading means the panel reset it."""
    if previous is None:
        return max(0, counter)
    last = int(previous.used_traffic or 0)
    return max(0, counter) if counter < last else counter - last


async def describe_charges(rows) -> list[LedgerEntry]:
    missing = [row for row in rows if row.billed_minutes is None and row.used_bytes is None]
    previous = await ResellerBillingSnapshotCRUD().get_previous_usage_snapshots(missing)

    entries: list[LedgerEntry] = []
    for row in rows:
        amount = int(row.billed_amount or 0)
        counter = int(row.used_traffic or 0)
        if row.billed_minutes is not None:
            minutes = int(row.billed_minutes or 0)
            rate = row.unit_price
            estimated = rate is None
            if rate is None and minutes:
                rate = amount * 60 / minutes
            entries.append(
                LedgerEntry(
                    id=int(row.id),
                    account_code=int(row.account_code),
                    kind="hourly",
                    charged_at=int(row.snapshot_at),
                    amount=amount,
                    period_start=int(row.snapshot_at),
                    used_bytes=None,
                    minutes=minutes,
                    unit_price=rate,
                    rate_estimated=estimated and rate is not None,
                    panel_counter=counter,
                    is_debt=bool(row.is_debt),
                )
            )
            continue

        used = row.used_bytes
        start = row.period_start
        if used is None:
            prior = previous.get(int(row.id))
            used = _usage_since(counter, prior)
            start = int(prior.snapshot_at) if prior is not None else None
        rate = row.unit_price
        estimated = rate is None
        if rate is None and used:
            rate = amount / (used / GB)
        entries.append(
            LedgerEntry(
                id=int(row.id),
                account_code=int(row.account_code),
                kind="usage",
                charged_at=int(row.snapshot_at),
                amount=amount,
                period_start=start,
                used_bytes=int(used),
                minutes=None,
                unit_price=rate,
                rate_estimated=estimated and rate is not None,
                panel_counter=counter,
                is_debt=bool(row.is_debt),
            )
        )
    return entries
