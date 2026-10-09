"""Admin panel reseller endpoints: guards that keep billing and panel state consistent."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.models.panel.common import PanelRequest
from app.models.panel.resellers import (
    PanelResellerChangePlanRequest,
    PanelResellerCodeRequest,
    PanelResellerDataLimitRequest,
    PanelResellerDetailRequest,
    PanelResellerPanelSettings,
    PanelResellerPlanDeleteRequest,
    PanelResellerPlanSaveRequest,
    PanelResellerSettingsSaveRequest,
    PanelResellerUpdateRequest,
)
from app.routers.panel import guard, reseller_settings, resellers
from app.routers.panel.auth import PanelActor


@pytest.fixture(autouse=True)
def admin(monkeypatch):
    async def authenticate(**kwargs):
        return PanelActor(user_id=1, ip="127.0.0.1")

    async def no_audit(**kwargs):
        return None

    monkeypatch.setattr(guard, "authenticate_admin", authenticate)
    monkeypatch.setattr(resellers.audit, "record", no_audit)


def _account(**overrides) -> SimpleNamespace:
    values = {
        "code": 5,
        "telegram_id": 7,
        "panel_code": 1,
        "panel_admin_id": 42,
        "plan_id": 3,
        "username": "res",
        "pricing_mode": "usage",
        "purchased_volume": None,
        "data_limit": None,
        "usage_cap_bytes": None,
        "max_users": 2,
        "createtime": 0,
        "expiration_time": None,
        "status": "active",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _plan(**overrides) -> SimpleNamespace:
    values = {
        "id": 3,
        "panel_code": 1,
        "pricing_mode": "usage",
        "price": 0,
        "unit_price": 1000,
        "data_limit": 0,
        "duration": 0,
        "max_users": 0,
        "enable": True,
        "role_id": 1,
        "role_name": "seller",
        "addon_day_price": 0,
        "addon_gb_price": 0,
        "addon_user_price": 300,
    }
    values.update(overrides)
    return SimpleNamespace(**values, display_button_text=None)


def _linked(monkeypatch, count: int) -> None:
    class Accounts:
        async def count_accounts_by_plan(self, plan_id):
            return count

    monkeypatch.setattr(resellers, "ResellerAccountCRUD", Accounts)


def test_admin_actions_follow_status_and_mode():
    assert "resume" in resellers.admin_actions(_account(status="admin_paused"))
    assert "pause" not in resellers.admin_actions(_account(status="expired"))
    assert "renew" in resellers.admin_actions(_account(pricing_mode="fixed"))
    assert "renew" in resellers.admin_actions(_account(pricing_mode="unlimited"))
    assert "renew" not in resellers.admin_actions(_account(pricing_mode="fixed", plan_id=None))
    assert "renew" not in resellers.admin_actions(_account(pricing_mode="hourly"))
    assert "extend" not in resellers.admin_actions(_account(expiration_time=None))
    assert "usage_cap" not in resellers.admin_actions(_account(pricing_mode="hourly"))
    assert "forgive_usage" in resellers.admin_actions(_account(pricing_mode="usage"))
    assert "forgive_usage" not in resellers.admin_actions(_account(pricing_mode="hourly"))
    assert "data_limit" not in resellers.admin_actions(_account(pricing_mode="unlimited"))
    assert "data_limit" in resellers.admin_actions(_account(pricing_mode="fixed"))
    assert "resync" in resellers.admin_actions(_account())
    assert "change_plan" not in resellers.admin_actions(_account(plan_id=None))


async def test_linked_plan_cannot_be_deleted(monkeypatch):
    _linked(monkeypatch, 4)
    deleted = []

    async def delete(actor, plan_id):
        deleted.append(plan_id)
        return True

    monkeypatch.setattr(resellers.mutations, "delete_reseller_plan", delete)
    result = await resellers.delete_reseller_plan(PanelResellerPlanDeleteRequest(plan_id=3), None)
    assert not result.ok
    assert deleted == []


async def _save(monkeypatch, request: PanelResellerPlanSaveRequest, *, linked: int, existing=None):
    _linked(monkeypatch, linked)
    saved, notices = [], []

    async def panel_names():
        return {1: "main", 2: "other"}

    async def get_plan(plan_id):
        return existing if existing is not None else _plan()

    async def upsert(actor, plan_id, values):
        saved.append(values)

    async def roles(panel_code):
        return [{"id": 1, "name": "seller"}, {"id": 2, "name": "vip"}]

    monkeypatch.setattr(resellers.queries, "panel_names", panel_names)
    monkeypatch.setattr(resellers.queries, "get_reseller_plan", get_plan)
    monkeypatch.setattr(resellers.mutations, "upsert_reseller_plan", upsert)
    monkeypatch.setattr(resellers, "_panel_roles", roles)
    monkeypatch.setattr(resellers, "_schedule_rate_notice", lambda *args: notices.append(args[1:3]))
    result = await resellers.save_reseller_plan(request, None)
    return result, saved, notices


async def test_linked_plan_keeps_its_pricing_mode(monkeypatch):
    request = PanelResellerPlanSaveRequest(
        plan_id=3, panel_code=1, pricing_mode="fixed", price=5000, data_limit_gb=10, duration=30, role_id=1
    )
    result, saved, _ = await _save(monkeypatch, request, linked=2)
    assert not result.ok
    assert saved == []


async def test_rate_change_on_linked_plan_notifies_resellers(monkeypatch):
    request = PanelResellerPlanSaveRequest(plan_id=3, panel_code=1, pricing_mode="usage", unit_price=1500, role_id=1)
    result, saved, notices = await _save(monkeypatch, request, linked=2)
    assert result.ok
    assert saved[0]["data_limit"] == 0
    assert notices == [(1000.0, 1500.0)]


async def test_free_usage_plan_is_rejected(monkeypatch):
    request = PanelResellerPlanSaveRequest(panel_code=1, pricing_mode="usage", unit_price=0, role_id=1)
    result, saved, _ = await _save(monkeypatch, request, linked=0)
    assert not result.ok
    assert saved == []


async def test_no_new_plans_of_a_legacy_type(monkeypatch):
    request = PanelResellerPlanSaveRequest(panel_code=1, pricing_mode="per_gb", unit_price=500, role_id=1)
    result, saved, _ = await _save(monkeypatch, request, linked=0)
    assert not result.ok
    assert saved == []


async def test_role_name_comes_from_the_panel(monkeypatch):
    request = PanelResellerPlanSaveRequest(
        panel_code=1,
        pricing_mode="fixed",
        price=900,
        data_limit_gb=10,
        duration=30,
        role_id=2,
        role_name="typed by hand",
    )
    result, saved, _ = await _save(monkeypatch, request, linked=0)
    assert result.ok
    assert (saved[0]["role_id"], saved[0]["role_name"]) == (2, "vip")


async def test_unknown_role_is_rejected(monkeypatch):
    request = PanelResellerPlanSaveRequest(
        panel_code=1, pricing_mode="fixed", price=900, data_limit_gb=10, duration=30, role_id=99
    )
    result, saved, _ = await _save(monkeypatch, request, linked=0)
    assert not result.ok
    assert saved == []


async def test_legacy_update_without_changes_touches_nothing(monkeypatch):
    async def get_reseller(code):
        return _account()

    async def must_not_run(*args, **kwargs):
        raise AssertionError("no service call expected")

    monkeypatch.setattr(resellers.queries, "get_reseller", get_reseller)
    for name in (
        "resume_account_by_admin",
        "pause_account_by_admin",
        "set_reseller_usage_cap",
        "set_max_users_by_admin",
    ):
        monkeypatch.setattr(resellers, name, must_not_run)
    result = await resellers.update_reseller(PanelResellerUpdateRequest(code=5, max_users=2), None)
    assert result.ok
    assert result.message == "تغییری برای ذخیره وجود نداشت."


async def test_detail_still_loads_when_the_panel_is_down(monkeypatch):
    async def get_reseller(code):
        return _account(pricing_mode="hourly")

    async def panel_names():
        return {1: "main"}

    async def empty(*args, **kwargs):
        return []

    async def boom(account):
        raise ConnectionError("panel unreachable")

    async def balances(ids):
        return {7: 9000}

    class Events:
        async def list_events(self, **kwargs):
            return [], 0

    class Plans:
        async def get_plan(self, plan_id):
            return _plan()

        async def get_all_plans(self, panel_code=None, enabled_only=False):
            return [_plan(), _plan(id=4), _plan(id=5, pricing_mode="usage"), _plan(id=6, panel_code=2)]

    class Accounts:
        async def get_accounts_by_user(self, telegram_id):
            return [_account(pricing_mode="hourly")]

    async def runway(balance, accounts):
        return SimpleNamespace(hours_left=9.0)

    monkeypatch.setattr(resellers.queries, "get_reseller", get_reseller)
    monkeypatch.setattr(resellers.queries, "panel_names", panel_names)
    monkeypatch.setattr(resellers.queries, "reseller_snapshots", empty)
    monkeypatch.setattr(resellers.queries, "user_balances", balances)
    monkeypatch.setattr(resellers, "ResellerEventCRUD", Events)
    monkeypatch.setattr(resellers, "ResellerPlanManager", Plans)
    monkeypatch.setattr(resellers, "ResellerAccountCRUD", Accounts)
    monkeypatch.setattr(resellers, "load_account_live_info", boom)
    monkeypatch.setattr(resellers, "estimate_runway", runway)

    result = await resellers.reseller_detail(PanelResellerDetailRequest(code=5), None)
    assert result.ok
    assert result.live is None and result.live_error
    assert result.plan.rate == 1000
    assert (result.balance, result.runway_hours) == (9000, 9.0)
    # Hourly accounts are never renewed; only same-panel plans of the account's type are offered.
    assert result.renew_plans == []
    assert result.change_plans == []
    assert result.plan_features["mode"] == "usage"


async def test_settings_ignore_the_old_capacity_price(monkeypatch):
    async def list_panels():
        return [SimpleNamespace(code=1, name="main", feature_settings=None)]

    patches, upserts = [], []

    def patch(panel, **kwargs):
        patches.append(kwargs)
        return {"patched": True}

    async def upsert(actor, code, values):
        upserts.append((code, values))

    monkeypatch.setattr(reseller_settings.queries, "list_panels", list_panels)
    monkeypatch.setattr(reseller_settings, "apply_feature_settings_patch", patch)
    monkeypatch.setattr(reseller_settings.mutations, "upsert_panel", upsert)
    request = PanelResellerSettingsSaveRequest(
        panels=[PanelResellerPanelSettings(code=1, capacity_enabled=True, capacity_price_per_user=0)],
    )
    result = await reseller_settings.save_reseller_settings(request, None)
    assert result.ok
    assert "reseller_capacity" not in patches[0]
    # A client that doesn't send the new toggles leaves the stored values alone instead of switching them on.
    assert "extra_days" not in patches[0]["reseller_buttons"]
    assert "extra_volume" not in patches[0]["reseller_buttons"]
    assert upserts == [(1, {"feature_settings": {"patched": True}})]


async def test_global_settings_are_clamped_when_read():
    setting = SimpleNamespace(
        reseller_sale_mode=True,
        reseller_min_wallet_balance=None,
        reseller_grace_days=0,
        reseller_low_balance_hours=5000,
        reseller_usage_debt=False,
    )
    result = reseller_settings._global_settings(setting)
    assert result.grace_days == 1
    assert result.low_balance_hours == 720
    assert result.min_wallet_balance == 100000
    assert result.usage_debt is False


# --------------------------------------------------------------------------- #
#  Plan save: the four plan types                                               #
# --------------------------------------------------------------------------- #

GB = 1024**3


@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        (
            {"pricing_mode": "fixed", "price": 90000, "data_limit_gb": 100, "duration": 30, "unit_price": 50},
            {"price": 90000, "unit_price": 0, "data_limit": 100 * GB, "duration": 30},
        ),
        (
            {"pricing_mode": "unlimited", "price": 120000, "data_limit_gb": 50, "duration": 30},
            {"price": 120000, "unit_price": 0, "data_limit": 0, "duration": 30},
        ),
        (
            {"pricing_mode": "usage", "unit_price": 900, "price": 5000, "data_limit_gb": 500, "duration": 30},
            {"price": 0, "unit_price": 900, "data_limit": 500 * GB, "duration": 0},
        ),
        (
            {"pricing_mode": "hourly", "unit_price": 200, "data_limit_gb": 0, "duration": 7},
            {"price": 0, "unit_price": 200, "data_limit": 0, "duration": 0},
        ),
    ],
)
async def test_each_plan_type_saves_normalized(monkeypatch, fields, expected):
    request = PanelResellerPlanSaveRequest(panel_code=1, role_id=1, max_users=50, **fields)
    result, saved, _ = await _save(monkeypatch, request, linked=0)
    assert result.ok, result.error
    for key, value in expected.items():
        assert saved[0][key] == value, key
    assert saved[0]["max_users"] == 50


@pytest.mark.parametrize(
    "fields",
    [
        {"pricing_mode": "fixed", "price": 9000, "data_limit_gb": 0, "duration": 30},
        {"pricing_mode": "fixed", "price": 9000, "data_limit_gb": 10, "duration": 0},
        {"pricing_mode": "fixed", "price": 0, "data_limit_gb": 10, "duration": 30},
        {"pricing_mode": "unlimited", "price": 9000, "duration": 0},
        {"pricing_mode": "unlimited", "price": 0, "duration": 30},
        {"pricing_mode": "usage", "unit_price": 0},
        {"pricing_mode": "hourly", "unit_price": 0},
        {"pricing_mode": "weekly", "price": 9000, "duration": 7},
    ],
)
async def test_invalid_plan_values_are_rejected(monkeypatch, fields):
    request = PanelResellerPlanSaveRequest(panel_code=1, role_id=1, **fields)
    result, saved, _ = await _save(monkeypatch, request, linked=0)
    assert not result.ok
    assert result.error
    assert saved == []


async def test_addon_prices_are_saved_and_cleared_when_the_type_lacks_them(monkeypatch):
    request = PanelResellerPlanSaveRequest(
        panel_code=1,
        role_id=1,
        pricing_mode="unlimited",
        price=100000,
        duration=30,
        addon_day_price=4000,
        addon_gb_price=2500,
        addon_user_price=1000,
    )
    result, saved, _ = await _save(monkeypatch, request, linked=0)
    assert result.ok
    # Unlimited has no volume, so the extra-volume price is cleared.
    assert (saved[0]["addon_day_price"], saved[0]["addon_gb_price"], saved[0]["addon_user_price"]) == (4000, 0, 1000)


async def test_addon_prices_left_out_on_edit_keep_the_stored_ones(monkeypatch):
    existing = _plan(
        pricing_mode="fixed",
        price=80000,
        unit_price=0,
        data_limit=20 * GB,
        duration=30,
        addon_day_price=3000,
        addon_gb_price=1500,
        addon_user_price=700,
    )
    request = PanelResellerPlanSaveRequest(
        plan_id=3, panel_code=1, role_id=1, pricing_mode="fixed", price=85000, duration=30, addon_gb_price=1800
    )
    result, saved, notices = await _save(monkeypatch, request, linked=2, existing=existing)
    assert result.ok, result.error
    assert saved[0]["data_limit"] == 20 * GB
    assert (saved[0]["addon_day_price"], saved[0]["addon_gb_price"], saved[0]["addon_user_price"]) == (3000, 1800, 700)
    # A fixed plan's price change only affects future purchases and renewals: no notice.
    assert notices == []


async def test_legacy_plan_stays_editable_as_its_own_type(monkeypatch):
    existing = _plan(pricing_mode="per_gb", unit_price=400)
    request = PanelResellerPlanSaveRequest(
        plan_id=3, panel_code=1, role_id=1, pricing_mode="per_gb", unit_price=450, min_volume=10, max_volume=100
    )
    result, saved, _ = await _save(monkeypatch, request, linked=1, existing=existing)
    assert result.ok, result.error
    assert saved[0]["unit_price"] == 450


async def test_legacy_fixed_plan_without_volume_must_be_fixed_on_edit(monkeypatch):
    existing = _plan(pricing_mode="fixed", price=50000, unit_price=0, data_limit=0, duration=30)
    request = PanelResellerPlanSaveRequest(
        plan_id=3, panel_code=1, role_id=1, pricing_mode="fixed", price=50000, duration=30
    )
    result, saved, _ = await _save(monkeypatch, request, linked=1, existing=existing)
    assert not result.ok
    assert saved == []


async def test_plan_cannot_switch_to_a_legacy_type(monkeypatch):
    request = PanelResellerPlanSaveRequest(plan_id=3, panel_code=1, role_id=1, pricing_mode="per_tb", unit_price=500)
    result, saved, _ = await _save(monkeypatch, request, linked=0)
    assert not result.ok
    assert saved == []


async def test_plans_list_exposes_addons_and_creatable_types(monkeypatch):
    plan = _plan(pricing_mode="fixed", price=5000, unit_price=0, data_limit=10 * GB, duration=30, addon_gb_price=900)
    plan.min_volume, plan.max_volume, plan.volume_step = 0, 0, 1
    plan.button_style, plan.button_icon = None, None

    async def list_plans():
        return [plan]

    async def panel_names():
        return {1: "main"}

    async def link_counts():
        return {3: 2}

    monkeypatch.setattr(resellers.queries, "list_reseller_plans", list_plans)
    monkeypatch.setattr(resellers.queries, "panel_names", panel_names)
    monkeypatch.setattr(resellers.queries, "reseller_plan_link_counts", link_counts)
    result = await resellers.list_reseller_plans(PanelRequest(), None)
    assert result.pricing_modes == ["fixed", "unlimited", "usage", "hourly"]
    row = result.plans[0]
    assert (row.addon_gb_price, row.addon_user_price, row.linked_accounts) == (900, 300, 2)
    assert row.features["extra_gb_price"] == 900 and row.features["renewable"] is True


# --------------------------------------------------------------------------- #
#  Admin repair tools                                                           #
# --------------------------------------------------------------------------- #


def _tool(monkeypatch, name: str, *, result=(True, "done"), account=None):
    calls, audits = [], []

    async def get_reseller(code):
        return account if account is not None else _account()

    async def service(acc, **kwargs):
        calls.append((acc.code, kwargs))
        return result

    async def record(**kwargs):
        audits.append(kwargs)

    monkeypatch.setattr(resellers.queries, "get_reseller", get_reseller)
    monkeypatch.setattr(resellers, name, service)
    monkeypatch.setattr(resellers.audit, "record", record)
    return calls, audits


async def test_data_limit_tool_sets_volume_and_records_it(monkeypatch):
    calls, audits = _tool(monkeypatch, "set_data_limit_by_admin")
    result = await resellers.set_reseller_data_limit(PanelResellerDataLimitRequest(code=5, add_gb=20), None)
    assert result.ok and result.message == "done"
    assert calls == [(5, {"set_gb": None, "add_gb": 20, "actor_id": 1})]
    assert audits[0]["action"] == "reseller_data_limit" and audits[0]["target_id"] == 5


async def test_data_limit_tool_needs_exactly_one_value(monkeypatch):
    calls, audits = _tool(monkeypatch, "set_data_limit_by_admin")
    result = await resellers.set_reseller_data_limit(PanelResellerDataLimitRequest(code=5), None)
    assert not result.ok
    result = await resellers.set_reseller_data_limit(PanelResellerDataLimitRequest(code=5, set_gb=5, add_gb=5), None)
    assert not result.ok
    assert calls == [] and audits == []


async def test_change_plan_tool_calls_service_and_records(monkeypatch):
    calls, audits = _tool(monkeypatch, "change_plan_by_admin")
    result = await resellers.change_reseller_plan(PanelResellerChangePlanRequest(code=5, plan_id=8), None)
    assert result.ok
    assert calls == [(5, {"plan_id": 8, "actor_id": 1})]
    assert audits[0]["action"] == "reseller_change_plan"
    assert audits[0]["detail"] == {"plan_before": 3, "plan_after": 8}


async def test_resync_tool_calls_service_and_records(monkeypatch):
    calls, audits = _tool(monkeypatch, "resync_with_panel")
    result = await resellers.resync_reseller(PanelResellerCodeRequest(code=5), None)
    assert result.ok
    assert calls == [(5, {"actor_id": 1})]
    assert audits[0]["action"] == "reseller_resync"


async def test_forgive_usage_tool_calls_service_and_records(monkeypatch):
    calls, audits = _tool(monkeypatch, "forgive_unbilled_usage")
    result = await resellers.forgive_reseller_usage(PanelResellerCodeRequest(code=5), None)
    assert result.ok
    assert calls == [(5, {"actor_id": 1})]
    assert audits[0]["action"] == "reseller_forgive_usage"


async def test_failed_tool_is_not_recorded(monkeypatch):
    calls, audits = _tool(monkeypatch, "forgive_unbilled_usage", result=(False, "nope"))
    result = await resellers.forgive_reseller_usage(PanelResellerCodeRequest(code=5), None)
    assert not result.ok and result.error == "nope"
    assert len(calls) == 1 and audits == []


async def test_tools_report_a_missing_account(monkeypatch):
    async def missing(code):
        return None

    monkeypatch.setattr(resellers.queries, "get_reseller", missing)
    for call, request in (
        (resellers.resync_reseller, PanelResellerCodeRequest(code=9)),
        (resellers.forgive_reseller_usage, PanelResellerCodeRequest(code=9)),
        (resellers.change_reseller_plan, PanelResellerChangePlanRequest(code=9, plan_id=2)),
        (resellers.set_reseller_data_limit, PanelResellerDataLimitRequest(code=9, set_gb=5)),
    ):
        result = await call(request, None)
        assert not result.ok and result.error == resellers.NOT_FOUND


async def test_detail_offers_own_plan_for_renewal_and_same_type_plans_for_change(monkeypatch):
    account = _account(pricing_mode="fixed", plan_id=3, data_limit=10 * GB, expiration_time=2_000_000_000)
    own = _plan(pricing_mode="fixed", price=5000, unit_price=0, data_limit=10 * GB, duration=30, enable=False)

    async def get_reseller(code):
        return account

    async def panel_names():
        return {1: "main"}

    async def empty(*args, **kwargs):
        return []

    async def live(acc):
        return SimpleNamespace(
            plan=own,
            used_traffic=0,
            data_limit=10 * GB,
            total_users=1,
            admin_status="active",
            login_url="",
            balance=None,
            billed_total=None,
            grace_days_left=None,
        )

    class Events:
        async def list_events(self, **kwargs):
            return [], 0

    class Plans:
        async def get_all_plans(self, panel_code=None, enabled_only=False):
            return [
                own,
                _plan(id=4, pricing_mode="fixed", price=7000),
                _plan(id=5, pricing_mode="unlimited", price=7000),
            ]

    class Settings:
        async def get_settings(self):
            return SimpleNamespace(reseller_grace_days=4)

    monkeypatch.setattr(resellers.queries, "get_reseller", get_reseller)
    monkeypatch.setattr(resellers.queries, "panel_names", panel_names)
    monkeypatch.setattr(resellers.queries, "reseller_snapshots", empty)
    monkeypatch.setattr(resellers, "ResellerEventCRUD", Events)
    monkeypatch.setattr(resellers, "ResellerPlanManager", Plans)
    monkeypatch.setattr(resellers, "SettingsManager", Settings)
    monkeypatch.setattr(resellers, "load_account_live_info", live)

    result = await resellers.reseller_detail(PanelResellerDetailRequest(code=5), None)
    assert result.ok
    assert [plan.id for plan in result.renew_plans] == [3]
    assert result.renew_plans[0].enable is False
    assert [plan.id for plan in result.change_plans] == [4]
    assert result.grace_days == 4
