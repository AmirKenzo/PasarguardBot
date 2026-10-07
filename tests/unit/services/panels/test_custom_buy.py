"""Unit tests for panel custom-buy pricing helpers."""

from types import SimpleNamespace

from app.services.panels.custom_buy import (
    CUSTOM_PLAN_ID,
    build_custom_buy_plan,
    is_custom_plan_id,
    validate_custom_days,
    validate_custom_gb,
)
from app.services.panels.settings import (
    FEATURE_CUSTOM_BUY,
    calculate_custom_buy_price,
    compact_feature_settings,
    panel_custom_buy_enabled,
    panel_custom_buy_settings,
    update_custom_buy_in_feature_settings,
)


def test_calculate_custom_buy_price():
    assert calculate_custom_buy_price(price_per_gb=5000, price_per_day=1000, storage_gb=30, duration_days=30) == 180_000
    assert calculate_custom_buy_price(price_per_gb=1000, price_per_day=500, storage_gb=1.5, duration_days=10) == 6500


def test_panel_custom_buy_enabled_requires_prices():
    panel = SimpleNamespace(
        feature_settings={FEATURE_CUSTOM_BUY: {"enabled": True, "price_per_gb": 0, "price_per_day": 1000}}
    )
    assert panel_custom_buy_enabled(panel) is False

    panel.feature_settings = {FEATURE_CUSTOM_BUY: {"enabled": True, "price_per_gb": 1000, "price_per_day": 500}}
    assert panel_custom_buy_enabled(panel) is True


def test_update_and_compact_custom_buy_settings():
    feature: dict = {}
    update_custom_buy_in_feature_settings(feature, enabled=True, price_per_gb=2000, price_per_day=300)
    compact = compact_feature_settings(feature)
    assert compact[FEATURE_CUSTOM_BUY]["enabled"] is True
    assert compact[FEATURE_CUSTOM_BUY]["price_per_gb"] == 2000
    assert compact[FEATURE_CUSTOM_BUY]["price_per_day"] == 300

    panel = SimpleNamespace(feature_settings=compact)
    settings = panel_custom_buy_settings(panel)
    assert settings["min_gb"] == 1
    assert settings["max_days"] == 365


def test_validate_custom_inputs():
    panel = SimpleNamespace(
        feature_settings={
            FEATURE_CUSTOM_BUY: {
                "enabled": True,
                "price_per_gb": 1000,
                "price_per_day": 500,
                "min_gb": 5,
                "max_gb": 100,
                "min_days": 7,
                "max_days": 90,
            }
        }
    )
    ok, err = validate_custom_gb(panel, "10")
    assert err is None and ok == 10
    bad, err = validate_custom_gb(panel, "2")
    assert bad is None and err

    days, err = validate_custom_days(panel, "30")
    assert err is None and days == 30
    bad_days, err = validate_custom_days(panel, "3")
    assert bad_days is None and err


def test_build_custom_plan_namespace():
    plan = build_custom_buy_plan(storage_gb=20, duration_days=15, price=25000, ip_limit=2)
    assert is_custom_plan_id(plan.id)
    assert is_custom_plan_id(CUSTOM_PLAN_ID)
    assert plan.storage == 20
    assert plan.duration == 15
    assert plan.price == 25000
    assert plan.ip_limit == 2
    assert plan.plan_type == "volume"
