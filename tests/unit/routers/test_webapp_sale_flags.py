"""Sale switches and per-service button flags are enforced server-side, not only in the UI."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.routers.webapp import services as services_module
from app.services import webapp_purchase

SETTINGS_ON = {
    "sale_mode": True,
    "copy_link_mode": True,
    "change_link_mode": True,
    "sub_mode": True,
    "tamdid_mode": True,
    "extension_mode": True,
    "upg_mode": True,
    "qr_mode": True,
    "other_links_mode": True,
    "transfer_config_mode": True,
    "client_list_mode": True,
    "usage_chart_mode": True,
}


def _settings(**overrides) -> SimpleNamespace:
    return SimpleNamespace(**{**SETTINGS_ON, **overrides})


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> dict:
    current = {"value": _settings()}

    async def get_settings(self):
        return current["value"]

    monkeypatch.setattr(services_module.SettingsManager, "get_settings", get_settings)
    monkeypatch.setattr(webapp_purchase.SettingsManager, "get_settings", get_settings)
    return current


def _panel(*, enable: bool = True, shop: bool = True, buttons: dict | None = None) -> SimpleNamespace:
    return SimpleNamespace(code=1, enable=enable, shop=shop, buttons=buttons or {})


@pytest.fixture
def panel_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(services_module, "panel_button_enabled", lambda panel, attr: panel.buttons.get(attr, True))
    monkeypatch.setattr(
        webapp_purchase, "panel_shop_sale_enabled", lambda panel: bool(panel and panel.enable and panel.shop)
    )


SERVICE = SimpleNamespace(is_test=False, package_size=0)


def _ensure(action: str, panel: SimpleNamespace) -> None:
    asyncio.run(services_module.ensure_service_action(SERVICE, panel, 1, action))


@pytest.mark.usefixtures("panel_flags")
@pytest.mark.parametrize(
    ("action", "setting", "button"),
    [
        ("tamdid", "tamdid_mode", "btn_tamdid"),
        ("extend_time", "extension_mode", "btn_zaman"),
        ("extra_volume", "upg_mode", "btn_hajm"),
        ("transfer_config", "transfer_config_mode", "btn_transfer"),
        ("change_link", "change_link_mode", "btn_change_link"),
        ("change_sub", "sub_mode", "btn_change_sub"),
        ("client_list", "client_list_mode", "btn_clients"),
        ("usage_chart", "usage_chart_mode", "btn_usage_chart"),
    ],
)
def test_service_action_follows_global_and_panel_flags(settings: dict, action: str, setting: str, button: str) -> None:
    _ensure(action, _panel())

    with pytest.raises(ValueError, match=services_module._ACTION_DISABLED_ERROR):
        _ensure(action, _panel(buttons={button: False}))

    settings["value"] = _settings(**{setting: False})
    with pytest.raises(ValueError, match=services_module._ACTION_DISABLED_ERROR):
        _ensure(action, _panel())


@pytest.mark.usefixtures("panel_flags")
def test_test_service_cannot_be_renewed(settings: dict) -> None:
    with pytest.raises(ValueError):
        asyncio.run(
            services_module.ensure_service_action(SimpleNamespace(is_test=True, package_size=0), _panel(), 1, "tamdid")
        )


@pytest.fixture
def purchase(
    monkeypatch: pytest.MonkeyPatch, settings: dict, panel_flags: None
) -> webapp_purchase.WebAppPurchaseService:
    service = webapp_purchase.WebAppPurchaseService()
    current_panel = {"value": _panel()}

    async def get_panel_by_code(code: int):
        return current_panel["value"]

    async def at_capacity(code: int) -> bool:
        return False

    async def get_plan(plan_id: int):
        return SimpleNamespace(id=plan_id, panel_code=1)

    monkeypatch.setattr(service.panels, "get_panel_by_code", get_panel_by_code)
    monkeypatch.setattr(service.panels, "is_panel_at_capacity", at_capacity)
    monkeypatch.setattr(service.plans, "get_plan", get_plan)
    service.current_panel = current_panel
    return service


def test_purchase_allowed_when_sale_is_open(purchase) -> None:
    _panel_obj, plan = asyncio.run(purchase._get_panel_plan(1, 5))
    assert plan.id == 5


def test_purchase_refused_when_global_sale_is_off(purchase, settings: dict) -> None:
    settings["value"] = _settings(sale_mode=False)
    with pytest.raises(ValueError):
        asyncio.run(purchase._get_panel_plan(1, 5))
    assert asyncio.run(purchase.get_panel_plans(1))["ok"] is False


def test_purchase_refused_when_panel_shop_sale_is_off(purchase) -> None:
    purchase.current_panel["value"] = _panel(shop=False)
    with pytest.raises(ValueError):
        asyncio.run(purchase._get_panel_plan(1, 5))
    assert asyncio.run(purchase.get_panel_plans(1))["ok"] is False
