"""Web app reseller endpoints: same toggles and server-side prices as the bot."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.models.webapp.common import WebAppAuthRequest
from app.models.webapp.reseller import (
    WebAppResellerBuyRequest,
    WebAppResellerCodeRequest,
    WebAppResellerPageRequest,
)
from app.routers.webapp import reseller
from app.services.reseller import ledger
from app.services.reseller.purchase import PriceQuote, PurchaseOutcome, PurchaseQuote

USER = 7


def _account(**overrides) -> SimpleNamespace:
    values = {
        "code": 5,
        "telegram_id": USER,
        "panel_code": 1,
        "username": "res",
        "pricing_mode": "usage",
        "status": "active",
        "expiration_time": None,
        "max_users": 0,
        "createtime": 0,
        "usage_cap_bytes": None,
        "purchased_volume": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.fixture
def env(monkeypatch):
    state = {"account": _account(), "actions": {"credentials", "delete"}, "locked": False}

    async def authenticate(**kwargs):
        return USER

    async def owned(code, telegram_id):
        account = state["account"]
        return account if code == account.code and telegram_id == account.telegram_id else None

    class Panels:
        async def get_panel_by_code(self, code):
            return SimpleNamespace(code=code, name="main")

    async def lock(user_id, name, ttl=None):
        return not state["locked"]

    async def unlock(user_id, name):
        return None

    monkeypatch.setattr(reseller, "authenticate_user", authenticate)
    monkeypatch.setattr(reseller, "get_owned_account", owned)
    monkeypatch.setattr(reseller, "PanelsManager", Panels)
    monkeypatch.setattr(reseller, "account_actions", lambda account, panel: frozenset(state["actions"]))
    monkeypatch.setattr(reseller, "acquire_user_lock", lock)
    monkeypatch.setattr(reseller, "release_user_lock", unlock)
    monkeypatch.setattr(reseller, "reveal_password", lambda account: "secret")
    return state


async def test_someone_elses_account_is_not_found(env):
    env["account"] = _account(telegram_id=999)
    result = await reseller.reseller_password(WebAppResellerCodeRequest(code=5))
    assert not result.ok
    assert result.password is None


async def test_disabled_button_is_refused_by_the_api(env):
    env["actions"] = {"delete"}
    result = await reseller.reseller_password(WebAppResellerCodeRequest(code=5))
    assert not result.ok
    assert result.password is None

    env["actions"] = {"credentials"}
    assert (await reseller.reseller_password(WebAppResellerCodeRequest(code=5))).password == "secret"


async def test_admin_locked_account_explains_why(env, monkeypatch):
    env["actions"] = {"delete"}
    monkeypatch.setattr(reseller, "is_admin_locked", lambda account: True)
    result = await reseller.reseller_pause(WebAppResellerCodeRequest(code=5))
    assert result.error == "این نمایندگی توسط ادمین غیرفعال شده است."


def _buy(**overrides) -> WebAppResellerBuyRequest:
    return WebAppResellerBuyRequest(**{"panel_code": 1, "plan_id": 3, "username": "shop_one", **overrides})


@pytest.fixture
def purchase(env, monkeypatch):
    calls = {"purchase": []}
    quote = PurchaseQuote(
        panel=SimpleNamespace(code=1, name="main"),
        plan=SimpleNamespace(id=3),
        volume=None,
        price=PriceQuote(base_price=1000, final_price=800, discount_percent=20, discount_code="OFF20"),
    )

    async def quote_purchase(user_id, **kwargs):
        return quote, None

    async def buy(user_id, **kwargs):
        calls["purchase"].append(kwargs)
        return PurchaseOutcome(True, account_code=55, password="pw", panel_url="https://p", new_balance=200)

    monkeypatch.setattr(reseller, "quote_reseller_purchase", quote_purchase)
    monkeypatch.setattr(reseller, "purchase_reseller_account", buy)
    return {"calls": calls, "quote": quote}


async def test_confirm_charges_the_server_price(purchase):
    result = await reseller.reseller_buy_confirm(_buy())
    assert result.ok and result.password == "pw"
    sent = purchase["calls"]["purchase"][0]
    assert (sent["amount"], sent["discount_code"], sent["username"]) == (800, "OFF20", "shop_one")


async def test_invalid_username_never_reaches_the_panel(purchase):
    result = await reseller.reseller_buy_confirm(_buy(username="bad name!"))
    assert not result.ok
    assert purchase["calls"]["purchase"] == []


async def test_wallet_rule_blocks_confirm(purchase):
    purchase["quote"].wallet_error = "need 100,000"
    result = await reseller.reseller_buy_confirm(_buy())
    assert result.error == "need 100,000"
    assert purchase["calls"]["purchase"] == []


async def test_double_submit_is_refused(env, purchase):
    env["locked"] = True
    result = await reseller.reseller_buy_confirm(_buy())
    assert not result.ok
    assert purchase["calls"]["purchase"] == []


async def test_closed_sale_hides_the_buy_card(env, monkeypatch):
    class Settings:
        async def get_settings(self):
            return SimpleNamespace(sale_mode=True, reseller_sale_mode=False)

    async def closed(settings=None):
        return False

    monkeypatch.setattr(reseller, "SettingsManager", Settings)
    monkeypatch.setattr(reseller, "reseller_sale_open", closed)
    result = await reseller.reseller_buy_options(WebAppAuthRequest())
    assert result.ok and result.enabled is False and result.panels == []


def _snap(row_id, at, counter_gb, amount, **extra):
    values = {
        "id": row_id,
        "account_code": 5,
        "snapshot_at": at,
        "used_traffic": counter_gb * 1024**3,
        "billed_amount": amount,
        "billed_minutes": None,
        "used_bytes": None,
        "unit_price": None,
        "period_start": None,
        "is_debt": None,
    }
    values.update(extra)
    return SimpleNamespace(**values)


async def test_usage_rows_explain_each_charge(env, monkeypatch):
    env["actions"] = {"usage_report"}
    gb = 1024**3
    rows = [
        # New row: stored usage, rate and period are reported as they are.
        _snap(3, 300, 9, 14_000, used_bytes=7 * gb, unit_price=2000.0, period_start=200),
        # Old row: usage rebuilt from the previous reading (counter reset 5 -> 2 GB), rate from amount/usage.
        _snap(2, 200, 2, 3_000),
        _snap(1, 100, 5, 20),
    ]

    class Snapshots:
        async def get_snapshots(self, code, limit, offset):
            return rows[offset : offset + limit]

        async def get_usage_totals(self, code):
            return 3, 17_020

        async def get_previous_usage_snapshots(self, targets):
            return {int(row.id): rows[rows.index(row) + 1] for row in targets if rows.index(row) + 1 < len(rows)}

    monkeypatch.setattr(reseller, "ResellerBillingSnapshotCRUD", Snapshots)
    monkeypatch.setattr(ledger, "ResellerBillingSnapshotCRUD", Snapshots)
    result = await reseller.reseller_usage(WebAppResellerPageRequest(code=5, limit=2))

    first, second = result.rows
    assert (first.used_bytes // gb, first.unit_price, first.period_start, first.rate_estimated) == (7, 2000, 200, False)
    assert (second.used_bytes // gb, second.unit_price, second.period_start, second.rate_estimated) == (
        2,
        1500,
        100,
        True,
    )
    assert result.has_more is True
    assert result.total_billed == 17_020
