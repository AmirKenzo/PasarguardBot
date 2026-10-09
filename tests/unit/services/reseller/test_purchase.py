"""Reseller purchase rollback paths: money and discount uses always come back on failure."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.reseller import purchase

PLAN = SimpleNamespace(
    id=3, panel_code=1, enable=True, pricing_mode="fixed", max_users=10, duration=30, data_limit=0, role_id=1
)


@pytest.fixture
def env(monkeypatch):
    calls: dict[str, list] = {"refund": [], "release": [], "removed": []}

    class Plans:
        async def get_plan(self, plan_id):
            return PLAN if plan_id == PLAN.id else None

    class Panels:
        async def get_panel_by_code(self, code):
            return SimpleNamespace(code=code)

    class Discounts:
        async def claim_discount_use(self, code, user_id):
            return True

        async def release_discount_use(self, code):
            calls["release"].append(code)

    class Accounts:
        insert_ok = True

        async def generate_unique_code(self):
            return 555

        async def create_account(self, **kwargs):
            return (True, None) if Accounts.insert_ok else (False, "db down")

        async def get_account(self, code):
            return True, SimpleNamespace(code=code)

    async def debit(user_id, amount):
        return env_state["debit_result"]

    async def refund(user_id, Money):
        calls["refund"].append(Money)

    async def username_exists(panel, username):
        return username == "taken"

    async def create_admin(panel, payload):
        return SimpleNamespace(id=9)

    async def remove_admin(panel, username):
        calls["removed"].append(username)

    async def no_log(*args, **kwargs):
        return None

    env_state = {"debit_result": 1000, "calls": calls, "accounts": Accounts}
    monkeypatch.setattr(purchase, "ResellerPlanManager", Plans)
    monkeypatch.setattr(purchase, "PanelsManager", Panels)
    monkeypatch.setattr(purchase, "DiscountCodeManager", Discounts)
    monkeypatch.setattr(purchase, "ResellerAccountCRUD", Accounts)
    monkeypatch.setattr(purchase, "debit_Money_if_sufficient", debit)
    monkeypatch.setattr(purchase, "update_Money", refund)
    monkeypatch.setattr(purchase, "admin_username_exists", username_exists)
    monkeypatch.setattr(purchase, "create_reseller_admin", create_admin)
    monkeypatch.setattr(purchase, "remove_reseller_admin", remove_admin)
    monkeypatch.setattr(purchase, "build_admin_create_payload", lambda plan, **kw: kw)
    monkeypatch.setattr(purchase, "send_reseller_log", no_log)
    monkeypatch.setattr(purchase, "get_panel_login_url", lambda panel: "https://panel")
    monkeypatch.setattr(purchase, "encrypt_data", lambda value: f"enc:{value}")
    return env_state


async def _buy(username: str = "ali_shop", discount: str | None = None):
    return await purchase.purchase_reseller_account(
        7, plan_id=PLAN.id, panel_code=1, username=username, volume=None, amount=500, discount_code=discount
    )


async def test_missing_plan_is_rejected(env):
    outcome = await purchase.purchase_reseller_account(
        7, plan_id=999, panel_code=1, username="x", volume=None, amount=500
    )
    assert outcome.error == purchase.ERR_MISSING_CONTEXT


async def test_taken_username_never_debits(env):
    outcome = await _buy(username="taken")
    assert outcome.error == purchase.ERR_USERNAME_EXISTS
    assert env["calls"]["refund"] == []


async def test_insufficient_balance_releases_discount(env):
    env["debit_result"] = None
    outcome = await _buy(discount="OFF10")
    assert outcome.error == purchase.ERR_INSUFFICIENT_BALANCE
    assert env["calls"]["release"] == ["OFF10"]


async def test_db_insert_failure_rolls_back_admin_money_and_discount(env):
    env["accounts"].insert_ok = False
    outcome = await _buy(discount="OFF10")
    assert outcome.error == purchase.ERR_ACCOUNT_INSERT_FAILED
    assert env["calls"]["removed"] == [9]
    assert env["calls"]["refund"] == [500]
    assert env["calls"]["release"] == ["OFF10"]


async def test_successful_purchase_returns_credentials(env):
    outcome = await _buy()
    assert outcome.ok
    assert outcome.account_code == 555
    assert outcome.panel_url == "https://panel"
    assert outcome.password
    assert outcome.new_balance == 1000


async def test_plan_from_another_panel_is_rejected(env):
    outcome = await purchase.purchase_reseller_account(
        7, plan_id=PLAN.id, panel_code=2, username="ali_shop", volume=None, amount=500
    )
    assert outcome.error == purchase.ERR_PLAN_UNAVAILABLE
    assert env["calls"]["refund"] == []
