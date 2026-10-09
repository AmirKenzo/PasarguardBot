"""Add-on purchases: quotes, wallet debit and refund when the panel step fails."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.reseller import addons
from app.services.reseller.plan_rules import ADDON_DAYS, ADDON_USERS, ADDON_VOLUME

GB = 1024**3
DAY = 86400
NOW = 1_700_000_000


def _account(**overrides):
    values = {
        "code": 5,
        "telegram_id": 7,
        "panel_admin_id": 9,
        "status": "active",
        "expiration_time": NOW + 10 * DAY,
        "data_limit": 100 * GB,
        "max_users": 20,
        "extra_users": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _plan(mode="fixed", **prices):
    values = {"addon_day_price": 1_000, "addon_gb_price": 500, "addon_user_price": 5_000}
    values.update(prices)
    return SimpleNamespace(pricing_mode=mode, **values)


@pytest.fixture
def env(monkeypatch):
    state = {"balance": 100_000, "debits": [], "refunds": [], "updates": [], "modified": [], "activated": []}
    state["fail"] = False
    admin = SimpleNamespace(data_limit=100 * GB, permission_overrides=None)

    async def debit(user_id, amount):
        if amount > state["balance"]:
            return None
        state["debits"].append(amount)
        return state["balance"] - amount

    async def refund(user_id, Money):
        state["refunds"].append(Money)

    async def get_admin(panel, admin_id):
        return admin

    async def modify(panel, admin_id, modify):
        if state["fail"]:
            raise RuntimeError("panel down")
        state["modified"].append(modify)

    async def activate(panel, admin_id):
        state["activated"].append(admin_id)

    async def update(self, code, **columns):
        state["updates"].append(columns)
        return True

    async def log(*args, **kwargs):
        return None

    monkeypatch.setattr(addons, "debit_Money_if_sufficient", debit)
    monkeypatch.setattr(addons, "update_Money", refund)
    monkeypatch.setattr(addons, "get_reseller_admin", get_admin)
    monkeypatch.setattr(addons, "modify_reseller_admin", modify)
    monkeypatch.setattr(addons, "activate_reseller_admin", activate)
    monkeypatch.setattr(addons.ResellerAccountCRUD, "update_account", update)
    monkeypatch.setattr(addons, "send_reseller_log", log)
    monkeypatch.setattr(addons, "Time_Date", lambda: {"stamp": NOW})
    return state


async def _buy(account, addon, quantity, plan=None, monkeypatch=None):
    return await addons.buy_addon(account, object(), plan or _plan(), addon, quantity, telegram_id=7)


@pytest.fixture(autouse=True)
def stored_row(monkeypatch):
    """The service re-reads the account; by default the stored row is the one the test passes."""
    rows: dict = {}
    original = addons.buy_addon

    async def buy(account, *args, **kwargs):
        rows.setdefault(account.code, account)
        return await original(account, *args, **kwargs)

    async def get_account(self, code):
        return (True, rows[code]) if code in rows else (False, "missing")

    monkeypatch.setattr(addons.ResellerAccountCRUD, "get_account", get_account)
    monkeypatch.setattr(addons, "buy_addon", buy)
    return rows


async def test_purchase_prices_from_the_stored_row_not_a_stale_copy(env, stored_row):
    # Another purchase already moved the expiry to +20 days; this request still holds the +10 copy.
    stored_row[5] = _account(expiration_time=NOW + 20 * DAY)
    ok, _, _ = await _buy(_account(expiration_time=NOW + 10 * DAY), ADDON_DAYS, 5)
    assert ok
    assert env["updates"] == [{"expiration_time": NOW + 25 * DAY}]


async def test_someone_elses_account_is_refused(env, stored_row):
    stored_row[5] = _account(telegram_id=99)
    ok, _, _ = await _buy(_account(), ADDON_DAYS, 1)
    assert not ok and env["debits"] == []


async def test_extra_days_extend_from_the_current_expiry(env):
    ok, _, _ = await _buy(_account(), ADDON_DAYS, 5)
    assert ok and env["debits"] == [5_000]
    assert env["updates"] == [{"expiration_time": NOW + 15 * DAY}]


async def test_extra_days_on_an_expired_account_count_from_now_and_switch_it_on(env):
    ok, _, _ = await _buy(_account(status="expired", expiration_time=NOW - 3 * DAY), ADDON_DAYS, 2)
    assert ok and env["activated"] == [9]
    assert env["updates"] == [{"expiration_time": NOW + 2 * DAY, "status": "active"}]


async def test_extra_volume_adds_to_the_panel_limit(env):
    ok, _, _ = await _buy(_account(), ADDON_VOLUME, 50)
    assert ok and env["debits"] == [25_000]
    assert env["modified"][0].data_limit == 150 * GB
    assert env["updates"] == [{"data_limit": 150 * GB}]


async def test_extra_users_are_counted_as_extra(env):
    ok, _, _ = await _buy(_account(extra_users=3), ADDON_USERS, 10)
    assert ok
    assert env["updates"] == [{"max_users": 30, "extra_users": 13}]


@pytest.mark.parametrize(
    ("overrides", "addon"),
    [
        ({"data_limit": 0}, ADDON_VOLUME),  # unlimited volume
        ({"max_users": 0}, ADDON_USERS),  # unlimited users
        ({"expiration_time": None}, ADDON_DAYS),  # never expires
        ({"status": "expired"}, ADDON_VOLUME),  # renew first
        ({"status": "admin_paused"}, ADDON_DAYS),  # admin lock
    ],
)
async def test_refused_addons_charge_nothing(env, overrides, addon):
    ok, _, _ = await _buy(_account(**overrides), addon, 1)
    assert not ok and env["debits"] == []


async def test_addon_switched_off_on_the_plan_is_refused(env):
    ok, _, _ = await _buy(_account(), ADDON_DAYS, 1, _plan(addon_day_price=0))
    assert not ok and env["debits"] == []


async def test_addon_the_plan_type_lacks_is_refused(env):
    ok, _, _ = await _buy(_account(), ADDON_VOLUME, 1, _plan("unlimited"))
    assert not ok and env["debits"] == []


async def test_insufficient_balance_changes_nothing(env):
    env["balance"] = 100
    ok, _, _ = await _buy(_account(), ADDON_DAYS, 5)
    assert not ok and env["updates"] == [] and env["modified"] == []


async def test_panel_failure_refunds_the_wallet(env):
    env["fail"] = True
    ok, _, _ = await _buy(_account(), ADDON_VOLUME, 10)
    assert not ok
    assert env["debits"] == [5_000] and env["refunds"] == [5_000]
    assert env["updates"] == []
