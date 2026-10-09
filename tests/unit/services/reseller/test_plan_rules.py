"""Plan type rules: what each type requires, clears and offers."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.reseller import plan_rules
from app.services.reseller.plan_rules import normalize_plan, plan_features, validate_plan

GB = 1024**3


def _values(mode: str, **overrides) -> dict:
    values = {
        "pricing_mode": mode,
        "price": 500_000,
        "unit_price": 2_500,
        "data_limit": 100 * GB,
        "duration": 30,
        "max_users": 10,
        "addon_day_price": 1_000,
        "addon_gb_price": 500,
        "addon_user_price": 5_000,
    }
    values.update(overrides)
    return values


@pytest.mark.parametrize("mode", ["fixed", "unlimited", "usage", "hourly"])
def test_every_creatable_type_saves_with_its_fields(mode):
    assert validate_plan(_values(mode)) is None


@pytest.mark.parametrize(
    ("mode", "field"),
    [
        ("fixed", "price"),
        ("fixed", "data_limit"),
        ("fixed", "duration"),
        ("unlimited", "price"),
        ("unlimited", "duration"),
        ("usage", "unit_price"),
        ("hourly", "unit_price"),
    ],
)
def test_required_field_at_zero_is_rejected(mode, field):
    assert validate_plan(_values(mode, **{field: 0}))


def test_usage_and_unlimited_accept_zero_volume():
    assert validate_plan(_values("usage", data_limit=0, duration=0)) is None
    assert validate_plan(_values("unlimited", data_limit=0)) is None


def test_legacy_type_is_only_editable_as_itself():
    assert validate_plan(_values("per_gb"))
    assert validate_plan(_values("per_gb"), existing_mode="per_gb") is None


def test_negative_addon_price_is_rejected():
    assert validate_plan(_values("fixed", addon_gb_price=-1))


def test_normalize_clears_what_the_type_does_not_use():
    unlimited = normalize_plan(_values("unlimited"))
    assert (unlimited["data_limit"], unlimited["unit_price"], unlimited["addon_gb_price"]) == (0, 0, 0)
    usage = normalize_plan(_values("usage"))
    assert (usage["duration"], usage["price"], usage["addon_day_price"], usage["addon_gb_price"]) == (0, 0, 0, 0)
    assert usage["data_limit"] == 100 * GB  # the optional traffic cap is kept
    fixed = normalize_plan(_values("fixed"))
    assert fixed["unit_price"] == 0 and fixed["addon_day_price"] == 1_000


def test_features_reflect_type_and_prices():
    features = plan_features(SimpleNamespace(**normalize_plan(_values("fixed"))))
    assert features["renewable"] and features["expires"]
    assert (features["extra_day_price"], features["extra_gb_price"], features["extra_user_price"]) == (
        1_000,
        500,
        5_000,
    )
    usage = plan_features(SimpleNamespace(**normalize_plan(_values("usage"))))
    assert not usage["renewable"] and not usage["expires"] and usage["usage_cap"]
    assert usage["extra_day_price"] == 0


def test_addon_price_is_zero_for_types_without_it():
    plan = SimpleNamespace(pricing_mode="unlimited", addon_gb_price=500)
    assert plan_rules.addon_price(plan, plan_rules.ADDON_VOLUME) == 0


def test_legacy_plan_keeps_its_duration_on_edit():
    assert normalize_plan(_values("per_gb", duration=30))["duration"] == 30
