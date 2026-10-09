"""Wallet runway: hourly plans burn their rate, usage plans their last-24h average."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.reseller import runway
from app.services.reseller.runway import estimate_runway, format_runway


def _account(code: int, mode: str, status: str = "active") -> SimpleNamespace:
    return SimpleNamespace(code=code, pricing_mode=mode, status=status, plan_id=None)


@pytest.fixture
def rates(monkeypatch):
    usage_totals: dict[int, int] = {}

    class Snapshots:
        async def sum_billed_since(self, codes, since):
            return {code: usage_totals[code] for code in codes if code in usage_totals}

    monkeypatch.setattr(runway, "ResellerBillingSnapshotCRUD", Snapshots)
    monkeypatch.setattr(runway, "resolve_live_unit_price", lambda account, plan: 1000)
    return usage_totals


async def test_hourly_rate_sets_the_runway(rates):
    result = await estimate_runway(5000, [_account(1, "hourly")])
    assert result.burn_per_hour == 1000
    assert result.hours_left == 5


async def test_usage_burn_is_the_daily_average(rates):
    rates[2] = 24_000  # 24k in the last day -> 1k/hour
    result = await estimate_runway(3000, [_account(2, "usage")])
    assert result.hours_left == 3


async def test_paused_and_fixed_accounts_do_not_burn(rates):
    result = await estimate_runway(3000, [_account(1, "hourly", status="paused"), _account(3, "fixed")])
    assert result.hours_left is None


def test_format_runway_picks_a_readable_unit():
    assert format_runway(None) == "—"
    assert format_runway(0.5) == "30 دقیقه"
    assert format_runway(5.2) == "5 ساعت"
    assert format_runway(72) == "3 روز"
