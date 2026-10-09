"""Renewal: only the plan that was bought, volume rollover, unlimited admins, discounts and locks."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.billing import reseller_renewal

GB = 1024**3


def _account(**overrides) -> SimpleNamespace:
    data = {
        "code": 5,
        "telegram_id": 7,
        "panel_code": 1,
        "panel_admin_id": 9,
        "plan_id": 3,
        "pricing_mode": "fixed",
        "status": "active",
        "data_limit": 100 * GB,
        "purchased_volume": None,
        "expiration_time": None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _plan(**overrides) -> SimpleNamespace:
    data = {"id": 3, "enable": True, "pricing_mode": "fixed", "panel_code": 1, "price": 50_000}
    data.update({"data_limit": 100 * GB, "duration": 30})
    data.update(overrides)
    return SimpleNamespace(**data)


@pytest.fixture
def env(monkeypatch):
    state = {
        "account": _account(),
        "plan": _plan(),
        "admin": SimpleNamespace(data_limit=100 * GB, used_traffic=40 * GB),
        "balance": 100_000,
        "modified": [],
        "updates": [],
        "debits": [],
    }

    async def get_account(self, code):
        return True, state["account"]

    async def get_plan(self, plan_id):
        return state["plan"]

    async def read_user(self, user_id):
        return SimpleNamespace(amount=state["balance"])

    async def get_panel(self, code):
        return object()

    async def get_admin(panel, admin_id):
        return state["admin"]

    async def modify(panel, admin_id, modify):
        state["modified"].append(modify.data_limit)

    async def activate(panel, admin_id):
        return None

    async def update(self, code, **kwargs):
        state["updates"].append(kwargs)
        return True

    async def debit(user_id, amount):
        state["debits"].append(amount)
        return state["balance"] - amount

    async def log(*args, **kwargs):
        return None

    monkeypatch.setattr(reseller_renewal.ResellerAccountCRUD, "get_account", get_account)
    monkeypatch.setattr(reseller_renewal.ResellerAccountCRUD, "update_account", update)
    monkeypatch.setattr(reseller_renewal.ResellerPlanManager, "get_plan", get_plan)
    monkeypatch.setattr(reseller_renewal.UserCRUD, "read_user", read_user)
    monkeypatch.setattr(reseller_renewal.PanelsManager, "get_panel_by_code", get_panel)
    monkeypatch.setattr(reseller_renewal, "get_reseller_admin", get_admin)
    monkeypatch.setattr(reseller_renewal, "modify_reseller_admin", modify)
    monkeypatch.setattr(reseller_renewal, "activate_reseller_admin", activate)
    monkeypatch.setattr(reseller_renewal, "debit_Money_if_sufficient", debit)
    monkeypatch.setattr(reseller_renewal, "send_reseller_log", log)
    return state


async def test_unused_volume_rolls_over(env):
    ok, _ = await reseller_renewal.renew_reseller_account(5, 3, 7)
    assert ok
    assert env["modified"] == [200 * GB]
    assert env["updates"][0]["data_limit"] == 200 * GB


async def test_another_plan_is_refused(env):
    ok, _ = await reseller_renewal.renew_reseller_account(5, 4, 7)
    assert not ok and env["debits"] == []


async def test_disabled_plan_still_renews(env):
    env["plan"] = _plan(enable=False)
    ok, _ = await reseller_renewal.renew_reseller_account(5, 3, 7)
    assert ok


async def test_unlimited_plan_renews_days_only(env):
    env["account"] = _account(pricing_mode="unlimited", data_limit=None)
    env["plan"] = _plan(pricing_mode="unlimited", data_limit=0)
    env["admin"] = SimpleNamespace(data_limit=0, used_traffic=900 * GB)
    ok, _ = await reseller_renewal.renew_reseller_account(5, 3, 7)
    assert ok
    assert env["modified"] == []  # the panel volume stays unlimited
    assert env["updates"][0]["data_limit"] is None


async def test_unlimited_admin_gets_the_plan_volume_on_top_of_its_usage(env):
    # An account bought on an old unlimited fixed plan: 0 + 100 GB would be used up at once.
    env["admin"] = SimpleNamespace(data_limit=0, used_traffic=500 * GB)
    env["account"] = _account(data_limit=None)
    ok, _ = await reseller_renewal.renew_reseller_account(5, 3, 7)
    assert ok
    assert env["modified"] == [600 * GB]


async def test_usage_account_cannot_renew(env):
    env["account"] = _account(pricing_mode="usage")
    ok, _ = await reseller_renewal.renew_reseller_account(5, 3, 7)
    assert not ok


async def test_full_discount_renews_for_free(env, monkeypatch):
    async def valid(self, code, user_id):
        return True, SimpleNamespace(code=code, discount_percentage=100)

    async def claim(self, code, user_id):
        return True

    monkeypatch.setattr(reseller_renewal.DiscountCodeManager, "validate_discount_code", valid)
    monkeypatch.setattr(reseller_renewal.DiscountCodeManager, "claim_discount_use", claim)
    ok, _ = await reseller_renewal.renew_reseller_account(5, 3, 7, amount=0, discount_code="FREE")
    assert ok
    assert env["debits"] == [0]


async def test_owner_cannot_renew_an_admin_locked_account(env):
    env["account"] = _account(status="admin_paused")
    ok, _ = await reseller_renewal.renew_reseller_account(5, 3, 7)
    assert not ok
    assert env["debits"] == []


async def test_admin_can_renew_a_locked_account_and_it_stays_locked(env):
    env["account"] = _account(status="admin_paused")
    ok, _ = await reseller_renewal.renew_reseller_account(5, 3, 7, actor_role="admin")
    assert ok
    assert env["updates"][0]["status"] == "admin_paused"


async def test_amount_from_the_caller_is_ignored(env):
    # A discounted amount shown for another account (or before a price rise) can't be reused.
    ok, _ = await reseller_renewal.renew_reseller_account(5, 3, 7, amount=1)
    assert ok
    assert env["debits"] == [50_000]


async def test_price_rise_after_preview_charges_the_current_price(env):
    env["plan"] = _plan(price=80_000)
    ok, _ = await reseller_renewal.renew_reseller_account(5, 3, 7, amount=50_000)
    assert ok
    assert env["debits"] == [80_000]
