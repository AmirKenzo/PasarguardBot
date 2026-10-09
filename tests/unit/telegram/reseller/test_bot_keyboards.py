"""Reseller keyboards follow the account's actions and the plan rules."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.reseller import accounts
from app.services.reseller.accounts import (
    ACTION_BUY_CAPACITY,
    ACTION_DELETE,
    ACTION_EXTRA_DAYS,
    ACTION_EXTRA_VOLUME,
    ACTION_PAUSE,
    ACTION_RENEW,
    ACTION_RESUME,
    account_actions,
)
from app.services.reseller.plan_rules import ADDON_DAYS, ADDON_USERS, ADDON_VOLUME
from app.telegram.admin.reseller_plans import states as plan_states
from app.telegram.admin.reseller_plans.callbacks import edit_error
from app.telegram.admin.reseller_plans.service import plan_manage_buttons
from app.telegram.keyboards.admin import admin_reseller_tools
from app.telegram.keyboards.registry import KEYBOARD_BUTTON_DEFAULTS, KEYBOARD_BUTTON_TITLES
from app.telegram.shared.keyboards.panel_buttons import PANEL_MS_RESELLER_BUTTON_TOGGLES
from app.telegram.user.reseller.keyboards import account_menu_actions, addon_preset_rows

GB = 1024**3


def _account(mode: str = "fixed", **overrides) -> SimpleNamespace:
    values = {
        "code": 123456,
        "pricing_mode": mode,
        "status": "active",
        "plan_id": 7,
        "expiration_time": 1,
        "data_limit": 10 * GB,
        "max_users": 50,
        "extra_users": 0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _plan(mode: str = "fixed", **overrides) -> SimpleNamespace:
    values = {
        "id": 7,
        "panel_code": 1,
        "pricing_mode": mode,
        "price": 100_000,
        "unit_price": 0,
        "data_limit": 10 * GB,
        "duration": 30,
        "max_users": 50,
        "addon_day_price": 1000,
        "addon_gb_price": 500,
        "addon_user_price": 2000,
        "min_volume": 0,
        "max_volume": 0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.fixture(autouse=True)
def all_buttons_on(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(accounts, "panel_reseller_button_enabled", lambda panel, key: True)


def test_menu_shows_every_addon_of_a_fixed_plan_in_order():
    actions = account_actions(_account(), panel=object(), plan=_plan())
    menu = account_menu_actions(actions)
    assert menu.index(ACTION_RENEW) < menu.index(ACTION_EXTRA_DAYS) < menu.index(ACTION_EXTRA_VOLUME)
    assert menu.index(ACTION_EXTRA_VOLUME) < menu.index(ACTION_BUY_CAPACITY) < menu.index(ACTION_DELETE)
    assert ACTION_PAUSE in menu


def test_menu_without_plan_has_no_addons():
    menu = account_menu_actions(account_actions(_account(), panel=object()))
    assert not {ACTION_EXTRA_DAYS, ACTION_EXTRA_VOLUME, ACTION_BUY_CAPACITY} & set(menu)


def test_unlimited_plan_menu_has_no_extra_volume():
    account = _account("unlimited", data_limit=0)
    menu = account_menu_actions(account_actions(account, panel=object(), plan=_plan("unlimited", data_limit=0)))
    assert ACTION_EXTRA_DAYS in menu
    assert ACTION_EXTRA_VOLUME not in menu
    assert ACTION_RENEW in menu


def test_resume_and_pause_never_both():
    assert account_menu_actions({ACTION_RESUME, ACTION_PAUSE}) == [ACTION_RESUME]


@pytest.mark.parametrize("addon", [ADDON_DAYS, ADDON_VOLUME, ADDON_USERS])
def test_addon_presets_fit_telegram_callback_limit(addon: str):
    rows = addon_preset_rows(99_999_999, addon)
    assert rows
    for row in rows:
        for _label, data in row:
            assert len(data.encode()) <= 64


def test_new_reseller_buttons_are_registered():
    for key in ("in.rs.extra_days", "in.rs.extra_volume", "in.rs.buy_user_capacity"):
        assert key in KEYBOARD_BUTTON_TITLES
        assert key in KEYBOARD_BUTTON_DEFAULTS
    assert "روز اضافه" in KEYBOARD_BUTTON_DEFAULTS["in.rs.extra_days"]
    assert "حجم اضافه" in KEYBOARD_BUTTON_DEFAULTS["in.rs.extra_volume"]
    assert "یوزر اضافه" in KEYBOARD_BUTTON_DEFAULTS["in.rs.buy_user_capacity"]


def test_panel_toggles_include_the_new_addons():
    toggles = dict(PANEL_MS_RESELLER_BUTTON_TOGGLES)
    assert "روز اضافه" in toggles["extra_days"]
    assert "حجم اضافه" in toggles["extra_volume"]
    assert "یوزر اضافه" in toggles["buy_user_capacity"]


def test_type_picker_offers_only_the_four_types():
    assert list(plan_states.PRICING_MODE_LABELS) == ["fixed", "unlimited", "usage", "hourly"]
    assert "ساعتی (بر اساس زمان فعال بودن)" in plan_states.PRICING_MODE_LABELS["hourly"]


def _callback_data(rows) -> list[str]:
    return [button.type.data.decode() for row in rows for button in row]


def test_plan_edit_buttons_follow_the_type():
    fixed = _callback_data(plan_manage_buttons(_plan()))
    for field in ("price", "data_limit", "duration", "addon_day_price", "addon_gb_price", "addon_user_price"):
        assert f"ResellerPlanEditField_7:{field}" in fixed
    hourly = _callback_data(plan_manage_buttons(_plan("hourly", price=0, unit_price=2000, duration=0)))
    assert "ResellerPlanEditField_7:unit_price" in hourly
    assert "ResellerPlanEditField_7:duration" not in hourly
    assert "ResellerPlanEditField_7:addon_day_price" not in hourly


def test_plan_edit_does_not_blame_an_old_error_on_an_unrelated_field():
    legacy = _plan(data_limit=0, duration=0)  # created before the rules
    assert edit_error(legacy, "duration", 30) is None
    assert edit_error(_plan(), "price", 0)


def test_admin_tools_follow_the_plan_type():
    fixed = [action for action, _ in admin_reseller_tools(_account())]
    assert {"days", "volume", "maxusers", "chplan", "resync"} <= set(fixed)
    assert "forgive" not in fixed
    usage = [action for action, _ in admin_reseller_tools(_account("usage", expiration_time=None))]
    assert "forgive" in usage
    assert "days" not in usage
    unlimited = [action for action, _ in admin_reseller_tools(_account("unlimited", data_limit=0))]
    assert "volume" not in unlimited


@pytest.mark.parametrize(
    "module",
    [
        "app.telegram.admin.reseller_plans.messages",
        "app.telegram.admin.reseller_plans.module",
        "app.telegram.admin.panels.messages",
        "app.telegram.admin.panels.callbacks",
        "app.telegram.admin.manage_user.messages",
        "app.telegram.admin.manage_user.callbacks",
        "app.telegram.user.reseller.messages",
        "app.telegram.user.reseller.module",
        "app.telegram.keyboards.customization",
    ],
)
def test_bot_modules_import(module: str):
    import importlib

    assert importlib.import_module(module)
