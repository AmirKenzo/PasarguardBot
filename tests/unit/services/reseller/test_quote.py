"""Server-side reseller pricing: the web app never trusts a client amount."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.reseller import purchase


def _plan(**overrides) -> SimpleNamespace:
    values = {
        "id": 3,
        "panel_code": 1,
        "enable": True,
        "pricing_mode": "fixed",
        "price": 1000,
        "unit_price": 0,
        "min_volume": 10,
        "max_volume": 100,
        "volume_step": 10,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.fixture
def env(monkeypatch):
    state = {"plan": _plan(), "sale": True, "panel_on": True, "discount": (True, None), "wallet_error": None}

    class Plans:
        async def get_plan(self, plan_id):
            return state["plan"] if plan_id == state["plan"].id else None

    class Panels:
        async def get_panel_by_code(self, code):
            return SimpleNamespace(code=code)

    class Discounts:
        async def validate_discount_code(self, code, user_id):
            return state["discount"]

    async def sale_open(settings=None):
        return state["sale"]

    async def wallet_error(plan, user_id):
        return state["wallet_error"]

    monkeypatch.setattr(purchase, "ResellerPlanManager", Plans)
    monkeypatch.setattr(purchase, "PanelsManager", Panels)
    monkeypatch.setattr(purchase, "DiscountCodeManager", Discounts)
    monkeypatch.setattr(purchase, "reseller_sale_open", sale_open)
    monkeypatch.setattr(purchase, "min_wallet_error", wallet_error)
    monkeypatch.setattr(purchase, "panel_reseller_sale_enabled", lambda panel: state["panel_on"])
    return state


async def _quote(**kwargs):
    return await purchase.quote_reseller_purchase(7, **{"panel_code": 1, "plan_id": 3, **kwargs})


async def test_closed_sale_and_disabled_panel_are_rejected(env):
    env["sale"] = False
    assert (await _quote())[0] is None
    env["sale"], env["panel_on"] = True, False
    assert (await _quote())[0] is None


async def test_plan_must_belong_to_the_panel_and_be_enabled(env):
    assert (await _quote(panel_code=2))[0] is None
    env["plan"] = _plan(enable=False)
    assert (await _quote())[0] is None


async def test_volume_plans_price_by_validated_volume(env):
    env["plan"] = _plan(pricing_mode="per_gb", unit_price=500)
    quote, _ = await _quote(volume=30)
    assert quote.price.final_price == 15_000
    assert (await _quote(volume=35))[0] is None
    assert (await _quote())[0] is None


async def test_discount_applies_only_to_fixed_plans(env):
    env["discount"] = (True, SimpleNamespace(code="OFF20", discount_percentage=20))
    quote, _ = await _quote(discount_code="off20")
    assert (quote.price.base_price, quote.price.final_price, quote.price.discount_code) == (1000, 800, "OFF20")

    env["plan"] = _plan(pricing_mode="hourly", price=0, unit_price=900)
    quote, error = await _quote(discount_code="OFF20")
    assert quote is None and error


async def test_wallet_rule_is_reported_not_raised(env):
    env["wallet_error"] = "need more"
    quote, error = await _quote()
    assert error is None
    assert quote.wallet_error == "need more"
