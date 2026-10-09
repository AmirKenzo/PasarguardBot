"""How migration c8d4f2a6e9b3 reads the old panel-wide extra-user price."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[3] / "app/db/migrations/versions/c8d4f2a6e9b3_add_reseller_plan_addons.py"


def _price(raw) -> int:
    spec = importlib.util.spec_from_file_location("c8d4f2a6e9b3", _PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module._panel_user_price(raw)


def test_enabled_panel_left_at_the_default_price_keeps_selling_at_2000():
    # The settings store only non-default values, so this panel has no price_per_user key at all.
    assert _price(json.dumps({"reseller_user_capacity": {"enabled": True}})) == 2000


@pytest.mark.parametrize(
    ("settings", "price"),
    [
        ({"reseller_user_capacity": {"enabled": True, "price_per_user": 5000}}, 5000),
        ({"reseller_user_capacity": {"enabled": True, "price_per_user": 0}}, 0),
        ({"reseller_user_capacity": {"enabled": True, "price_per_user": None}}, 2000),
        ({"reseller_user_capacity": {"enabled": False}}, 0),
        ({"reseller_user_capacity": {"price_per_user": 3000}}, 0),
        ({}, 0),
    ],
)
def test_price_per_case(settings, price):
    assert _price(settings) == price
    assert _price(json.dumps(settings)) == price
