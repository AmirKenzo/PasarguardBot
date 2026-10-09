"""Web app reseller endpoints: same toggles and server-side prices as the bot."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.models.webapp.common import WebAppAuthRequest
from app.models.webapp.reseller import (
    WebAppResellerAddonRequest,
    WebAppResellerBuyRequest,
    WebAppResellerCapacityRequest,
    WebAppResellerCodeRequest,
    WebAppResellerPageRequest,
    WebAppResellerRenewRequest,
)
from app.routers.webapp import reseller
from app.services.panels.settings import FEATURE_RESELLER_BUTTONS
from app.services.reseller import ledger
from app.services.reseller.purchase import PriceQuote, PurchaseOutcome, PurchaseQuote
from app.utils.formatting.dates import Time_Date

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
        "plan_id": None,
        "data_limit": 0,
        "extra_users": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.fixture
def env(monkeypatch):
    state = {"account": _account(), "actions": {"credentials", "delete"}, "locked": False, "plans": {}}

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

    class Plans:
        async def get_plan(self, plan_id):
            return state["plans"].get(plan_id)

    def actions(account, panel, plan=None):
        state["actions_plan"] = plan
        return frozenset(state["actions"])

    monkeypatch.setattr(reseller, "ResellerPlanManager", Plans)
    monkeypatch.setattr(reseller, "account_actions", actions)
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


# --------------------------------------------------------------------------- #
#  Plans, renewal and add-ons                                                   #
# --------------------------------------------------------------------------- #

DAY = 86400


def _plan(**overrides) -> SimpleNamespace:
    values = {
        "id": 3,
        "panel_code": 1,
        "pricing_mode": "fixed",
        "display_button_text": "Gold",
        "enable": True,
        "price": 300_000,
        "unit_price": 0,
        "min_volume": 0,
        "max_volume": 0,
        "volume_step": 1,
        "data_limit": 100 * 1024**3,
        "duration": 30,
        "max_users": 20,
        "addon_day_price": 2_000,
        "addon_gb_price": 1_500,
        "addon_user_price": 4_000,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.fixture
def fixed(env, monkeypatch):
    plan = _plan()
    env["plans"] = {3: plan}
    env["account"] = _account(
        pricing_mode="fixed",
        plan_id=3,
        expiration_time=Time_Date()["stamp"] + 10 * DAY,
        data_limit=100 * 1024**3,
        max_users=25,
        extra_users=5,
    )
    calls: dict[str, list] = {"buy_addon": [], "renew": []}

    async def balance(user_id):
        return 50_000

    async def buy(account, panel, plan_, addon, quantity, **kwargs):
        calls["buy_addon"].append((account, panel, plan_, addon, quantity, kwargs))
        return True, "done", None

    async def renew(*args, **kwargs):
        calls["renew"].append((args, kwargs))
        return True, "renewed"

    async def discount(user_id, base_price, code):
        return PriceQuote(base_price=base_price, final_price=base_price), None

    monkeypatch.setattr(reseller, "_balance", balance)
    monkeypatch.setattr(reseller, "buy_addon", buy)
    monkeypatch.setattr(reseller, "renew_reseller_account", renew)
    monkeypatch.setattr(reseller, "apply_reseller_discount", discount)
    return {"plan": plan, "calls": calls}


def _addon(**overrides) -> WebAppResellerAddonRequest:
    return WebAppResellerAddonRequest(**{"code": 5, "addon": "extra_days", "quantity": 5, **overrides})


async def test_addon_preview_prices_from_the_plan(env, fixed):
    env["actions"] = {"extra_days"}
    result = await reseller.reseller_addon_preview(_addon())
    assert result.ok, result.error
    assert (result.unit_price, result.total, result.balance_after, result.can_pay) == (2_000, 10_000, 40_000, True)
    assert result.after - result.before == 5 * DAY
    assert env["actions_plan"] is fixed["plan"]


async def test_addon_preview_volume_shows_bytes_before_and_after(env, fixed):
    env["actions"] = {"extra_volume"}
    result = await reseller.reseller_addon_preview(_addon(addon="extra_volume", quantity=10))
    assert result.ok, result.error
    assert result.total == 15_000
    assert result.after - result.before == 10 * 1024**3


async def test_addon_refused_when_action_is_hidden(env, fixed):
    env["actions"] = {"delete"}
    preview = await reseller.reseller_addon_preview(_addon())
    confirm = await reseller.reseller_addon_confirm(_addon())
    assert not preview.ok and preview.error == "این عملیات برای این نمایندگی فعال نیست."
    assert not confirm.ok
    assert fixed["calls"]["buy_addon"] == []


async def test_addon_confirm_refused_while_locked(env, fixed):
    env["actions"] = {"extra_days"}
    env["locked"] = True
    result = await reseller.reseller_addon_confirm(_addon())
    assert result.error == reseller.LOCK_BUSY
    assert fixed["calls"]["buy_addon"] == []


async def test_addon_confirm_buys_through_the_service(env, fixed):
    env["actions"] = {"extra_volume"}
    result = await reseller.reseller_addon_confirm(_addon(addon="extra_volume", quantity=10))
    assert result.ok and result.message == "done" and result.new_balance == 50_000
    account, _, plan, addon, quantity, kwargs = fixed["calls"]["buy_addon"][0]
    assert (account.code, plan.id, addon, quantity) == (5, 3, "extra_volume", 10)
    assert kwargs["telegram_id"] == USER and kwargs["source"] == "webapp"


async def test_addon_confirm_reports_service_refusal(env, fixed, monkeypatch):
    env["actions"] = {"extra_days"}

    async def refuse(*args, **kwargs):
        return False, "موجودی کافی نیست.", None

    monkeypatch.setattr(reseller, "buy_addon", refuse)
    result = await reseller.reseller_addon_confirm(_addon())
    assert not result.ok and result.error == "موجودی کافی نیست."


async def test_old_capacity_endpoints_use_the_plan_price(env, fixed):
    env["actions"] = {"buy_user_capacity"}
    preview = await reseller.reseller_capacity_preview(WebAppResellerCapacityRequest(code=5, quantity=10))
    assert preview.ok, preview.error
    assert (preview.price_per_user, preview.total_price, preview.limit_before, preview.limit_after) == (
        4_000,
        40_000,
        25,
        35,
    )
    confirm = await reseller.reseller_capacity_confirm(WebAppResellerCapacityRequest(code=5, quantity=10))
    assert confirm.ok
    assert fixed["calls"]["buy_addon"][0][3:5] == ("buy_user_capacity", 10)


async def test_renew_refuses_another_plan(env, fixed):
    env["actions"] = {"renew"}
    env["plans"][4] = _plan(id=4, price=100_000)
    request = WebAppResellerRenewRequest(code=5, plan_id=4)
    preview = await reseller.reseller_renew_preview(request)
    confirm = await reseller.reseller_renew_confirm(request)
    assert preview.error == reseller.RENEW_OWN_PLAN_ONLY
    assert confirm.error == reseller.RENEW_OWN_PLAN_ONLY
    assert fixed["calls"]["renew"] == []


async def test_renew_preview_adds_days_and_volume(env, fixed):
    env["actions"] = {"renew"}
    fixed["plan"].enable = False  # off sale for new buyers, still renewable
    result = await reseller.reseller_renew_preview(WebAppResellerRenewRequest(code=5, plan_id=3))
    assert result.ok, result.error
    assert result.final_price == 300_000 and result.can_pay is False
    assert result.expiry_after - result.expiry_before == 30 * DAY
    assert result.data_limit_after - result.data_limit_before == 100 * 1024**3
    assert result.max_users == 25

    confirm = await reseller.reseller_renew_confirm(WebAppResellerRenewRequest(code=5, plan_id=3))
    assert confirm.ok
    assert fixed["calls"]["renew"][0][0][:2] == (5, 3)


async def test_account_returns_features_and_only_its_own_plan(env, fixed, monkeypatch):
    env["actions"] = {"renew", "extra_days", "buy_user_capacity"}
    fixed["plan"].enable = False

    async def live(account):
        raise RuntimeError("panel down")

    class Settings:
        async def get_settings(self):
            return SimpleNamespace(reseller_grace_days=5, reseller_min_wallet_balance=100_000)

    class Events:
        async def list_events(self, **kwargs):
            return [], 0

    monkeypatch.setattr(reseller, "load_account_live_info", live)
    monkeypatch.setattr(reseller, "SettingsManager", Settings)
    monkeypatch.setattr(reseller, "ResellerEventCRUD", Events)
    result = await reseller.reseller_account(WebAppResellerCodeRequest(code=5))

    assert result.ok, result.error
    assert [(item.id, item.price, item.enabled) for item in result.renew_plans] == [(3, 300_000, False)]
    assert result.features.renewable and result.features.expires
    assert (result.features.extra_day_price, result.features.extra_gb_price) == (2_000, 1_500)
    assert result.capacity_price_per_user == 4_000
    assert (result.plan_max_users, result.extra_users, result.grace_days) == (20, 5, 5)
    assert set(result.addon_presets) == {"extra_days", "buy_user_capacity"}
    assert result.live is False


def test_panel_toggle_hides_addon_in_features():
    panel = SimpleNamespace(feature_settings={FEATURE_RESELLER_BUTTONS: {"extra_days": False, "usage_cap": False}})
    features = reseller._plan_features(_plan(), panel)
    assert features.extra_day_price == 0 and features.extra_gb_price == 1_500
    usage = reseller._plan_features(_plan(pricing_mode="usage", duration=0, unit_price=3_000), panel)
    assert usage.usage_cap is False and usage.needs_wallet and not usage.renewable
