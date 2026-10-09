"""Admin panel reseller endpoints: guards that keep billing and panel state consistent."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.models.panel.resellers import (
    PanelResellerDetailRequest,
    PanelResellerGlobalSettings,
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
        "role_id": 1,
        "role_name": "seller",
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
    assert "extend" not in resellers.admin_actions(_account(expiration_time=None))
    assert "usage_cap" not in resellers.admin_actions(_account(pricing_mode="hourly"))


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


async def _save(monkeypatch, request: PanelResellerPlanSaveRequest, *, linked: int):
    _linked(monkeypatch, linked)
    saved, notices = [], []

    async def panel_names():
        return {1: "main", 2: "other"}

    async def get_plan(plan_id):
        return _plan()

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
    request = PanelResellerPlanSaveRequest(plan_id=3, panel_code=1, pricing_mode="fixed", price=5000, role_id=1)
    result, saved, _ = await _save(monkeypatch, request, linked=2)
    assert not result.ok
    assert saved == []


async def test_rate_change_on_linked_plan_notifies_resellers(monkeypatch):
    request = PanelResellerPlanSaveRequest(plan_id=3, panel_code=1, pricing_mode="usage", unit_price=1500, role_id=1)
    result, saved, notices = await _save(monkeypatch, request, linked=2)
    assert result.ok
    assert "data_limit" not in saved[0]
    assert notices == [(1000.0, 1500.0)]


async def test_free_usage_plan_is_rejected(monkeypatch):
    request = PanelResellerPlanSaveRequest(panel_code=1, pricing_mode="usage", unit_price=0, role_id=1)
    result, saved, _ = await _save(monkeypatch, request, linked=0)
    assert not result.ok
    assert saved == []


async def test_new_plans_are_only_fixed_or_usage(monkeypatch):
    request = PanelResellerPlanSaveRequest(panel_code=1, pricing_mode="hourly", unit_price=500, role_id=1)
    result, saved, _ = await _save(monkeypatch, request, linked=0)
    assert not result.ok
    assert saved == []


async def test_role_name_comes_from_the_panel(monkeypatch):
    request = PanelResellerPlanSaveRequest(
        panel_code=1, pricing_mode="fixed", price=900, role_id=2, role_name="typed by hand"
    )
    result, saved, _ = await _save(monkeypatch, request, linked=0)
    assert result.ok
    assert (saved[0]["role_id"], saved[0]["role_name"]) == (2, "vip")


async def test_unknown_role_is_rejected(monkeypatch):
    request = PanelResellerPlanSaveRequest(panel_code=1, pricing_mode="fixed", price=900, role_id=99)
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


async def test_settings_refuse_capacity_without_a_price(monkeypatch):
    async def list_panels():
        return [SimpleNamespace(code=1, name="main")]

    monkeypatch.setattr(reseller_settings.queries, "list_panels", list_panels)
    request = PanelResellerSettingsSaveRequest(
        settings=PanelResellerGlobalSettings(grace_days=3),
        panels=[PanelResellerPanelSettings(code=1, capacity_enabled=True, capacity_price_per_user=0)],
    )
    result = await reseller_settings.save_reseller_settings(request, None)
    assert not result.ok


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
