"""Reseller billing math: panel usage resets and fractional hourly charges."""

from __future__ import annotations

import json
from types import SimpleNamespace

from app.jobs.reseller import billing
from app.services.reseller.usage_meter import usage_delta


def test_usage_delta_is_difference_since_last_charge():
    assert usage_delta(1500, 1000) == 500


def test_usage_delta_without_baseline_is_everything():
    # A new admin starts at 0, so everything it has used is new.
    assert usage_delta(1500, None) == 1500


def test_usage_delta_after_panel_reset_counts_new_usage():
    # Panel reset usage to 0 and the admin has since used 200 bytes.
    assert usage_delta(200, 10_000) == 200


async def _run_hourly(monkeypatch, *, rate: int, minutes: int, carry: float = 0.0, balance_ok: bool = True):
    now = 1_000_000
    state = {"last_billed_at": now - minutes * 60, "hourly_carry": carry}
    account = SimpleNamespace(
        code=1, telegram_id=7, panel_code=1, username="res", billing_state=json.dumps(state), createtime=0
    )
    patches: list[dict] = []
    debits: list[int] = []
    ledger: list[tuple[int, int]] = []

    async def fake_patch(self, code, *, updates=None, remove=(), **columns):
        patches.append(dict(updates or {}))
        return updates

    async def fake_debit(user_id, amount):
        debits.append(amount)
        return 100 if balance_ok else None

    async def fake_ledger(self, account_code, amount, minutes, charged_at, hourly_rate=None):
        assert hourly_rate == rate
        ledger.append((amount, minutes))
        return True

    monkeypatch.setattr(billing.ResellerAccountCRUD, "patch_billing_state", fake_patch)
    monkeypatch.setattr(billing, "debit_Money_if_sufficient", fake_debit)
    monkeypatch.setattr(billing.ResellerBillingSnapshotCRUD, "add_hourly_charge", fake_ledger)
    monkeypatch.setattr(billing, "resolve_live_unit_price", lambda account, plan: rate)

    await billing._process_hourly_account(account, None, now, plan=SimpleNamespace())
    return patches, debits, ledger


async def test_cheap_hourly_plan_is_not_overcharged(monkeypatch):
    # 20 T/h for one minute is 0.33 T: nothing is debited, the remainder is carried.
    patches, debits, ledger = await _run_hourly(monkeypatch, rate=20, minutes=1)
    assert debits == []
    assert ledger == []
    assert patches[-1]["hourly_carry"] == round(20 / 60, 6)


async def test_carry_is_billed_once_it_reaches_a_toman(monkeypatch):
    patches, debits, _ = await _run_hourly(monkeypatch, rate=20, minutes=1, carry=0.7)
    assert debits == [1]
    assert 0 <= patches[-1]["hourly_carry"] < 1


async def test_full_hour_charges_exact_rate(monkeypatch):
    _, debits, ledger = await _run_hourly(monkeypatch, rate=1000, minutes=60)
    assert debits == [1000]
    # The charge lands in the hourly ledger instead of a log-channel message.
    assert ledger == [(1000, 60)]
