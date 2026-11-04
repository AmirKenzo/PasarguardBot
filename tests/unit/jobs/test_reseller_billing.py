"""Reseller billing math: panel usage resets and fractional hourly charges."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

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


@pytest.mark.parametrize(
    ("suspend_fails", "admin_on_panel", "panel_up", "switched_off"),
    [
        (False, True, True, True),  # normal: suspended
        (True, False, True, True),  # admin deleted on the panel: already off, may expire
        (True, True, True, False),  # suspend failed on a live admin: retry next run
        (True, True, False, False),  # panel unreachable: retry next run
    ],
)
async def test_expiry_switches_the_admin_off_or_retries(
    monkeypatch, suspend_fails, admin_on_panel, panel_up, switched_off
):
    async def suspend(panel, admin_id):
        if suspend_fails:
            raise RuntimeError("suspend failed")

    async def get_admin(panel, admin_id):
        if not panel_up:
            raise RuntimeError("panel down")
        return SimpleNamespace(id=admin_id) if admin_on_panel else None

    monkeypatch.setattr(billing, "suspend_reseller_admin", suspend)
    monkeypatch.setattr(billing, "get_reseller_admin", get_admin)
    account = SimpleNamespace(code=1, panel_admin_id=9)
    assert await billing._switch_off_for_expiry(object(), account) is switched_off


async def test_unreachable_panel_does_not_abort_reactivation(monkeypatch):
    # The first account's panel times out; the second account must still be reactivated.
    accounts = [
        SimpleNamespace(code=1, telegram_id=7, panel_code=1, pricing_mode="usage", panel_admin_id=11, plan_id=None),
        SimpleNamespace(code=2, telegram_id=8, panel_code=1, pricing_mode="hourly", panel_admin_id=12, plan_id=None),
    ]
    reactivated: list[int] = []

    async def fake_accounts(self, status):
        return accounts

    async def fake_panels(self):
        return [SimpleNamespace(code=1)]

    async def fake_user(self, telegram_id):
        return SimpleNamespace(amount=1_000_000)

    async def fake_plan(account, *, plans_by_id):
        return None

    async def fake_admin(panel, admin_id):
        raise TimeoutError("panel unreachable")

    async def fake_reactivate(account, panel, *, stats=None):
        reactivated.append(account.code)

    monkeypatch.setattr(billing.ResellerAccountCRUD, "get_accounts_by_status", fake_accounts)
    monkeypatch.setattr(billing.PanelsManager, "get_all_panels", fake_panels)
    monkeypatch.setattr(billing.UserCRUD, "read_user", fake_user)
    monkeypatch.setattr(billing, "_resolve_plan", fake_plan)
    monkeypatch.setattr(billing, "resolve_live_unit_price", lambda account, plan: 100)
    monkeypatch.setattr(billing, "_reactivation_balance_needed", lambda account, *, hourly_rate: 1)
    monkeypatch.setattr(billing, "get_reseller_admin", fake_admin)
    monkeypatch.setattr(billing, "_reactivate_account", fake_reactivate)

    stats = billing._BillingRunStats()
    await billing._try_reactivate_suspended(None, stats=stats)

    assert reactivated == [2]
    assert stats.errors == 1
