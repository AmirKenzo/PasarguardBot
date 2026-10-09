"""Every reseller setting in one place: the global billing rules plus each panel's reseller switches."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from app.db.crud.settings import SettingsManager
from app.db.models.settings import DEFAULT_RESELLER_SETTINGS
from app.models.panel.common import ActionResponse, PanelRequest
from app.models.panel.resellers import (
    PanelResellerButtons,
    PanelResellerGlobalSettings,
    PanelResellerPanelSettings,
    PanelResellerSettingsResponse,
    PanelResellerSettingsSaveRequest,
)
from app.panel import audit, mutations, queries
from app.routers.panel import guard
from app.routers.panel.auth import PanelActor
from app.services.panels.settings import (
    apply_feature_settings_patch,
    panel_reseller_button_settings,
    panel_reseller_capacity_settings,
    panel_reseller_sale_flag,
)

router = APIRouter()

# API field -> stored ``reseller_settings`` key.
GLOBAL_KEYS: dict[str, str] = {
    "sale_mode": "reseller_sale_mode",
    "min_wallet_balance": "reseller_min_wallet_balance",
    "grace_days": "reseller_grace_days",
    "low_balance_hours": "reseller_low_balance_hours",
    "usage_debt": "reseller_usage_debt",
}


def _clamp(value: Any, default: int, low: int, high: int) -> int:
    try:
        return min(high, max(low, int(value)))
    except TypeError, ValueError:
        return default


def _global_settings(setting) -> PanelResellerGlobalSettings:
    def stored(field: str) -> Any:
        key = GLOBAL_KEYS[field]
        value = getattr(setting, key, None) if setting is not None else None
        return DEFAULT_RESELLER_SETTINGS[key] if value is None else value

    return PanelResellerGlobalSettings(
        sale_mode=bool(stored("sale_mode")),
        min_wallet_balance=_clamp(stored("min_wallet_balance"), 0, 0, 10**12),
        grace_days=_clamp(stored("grace_days"), 7, 1, 365),
        low_balance_hours=_clamp(stored("low_balance_hours"), 6, 1, 720),
        usage_debt=bool(stored("usage_debt")),
    )


def _panel_settings(panel) -> PanelResellerPanelSettings:
    capacity = panel_reseller_capacity_settings(panel)
    return PanelResellerPanelSettings(
        code=int(panel.code),
        name=panel.name or "",
        enable=bool(panel.enable),
        sale_enabled=panel_reseller_sale_flag(panel),
        capacity_enabled=bool(capacity["enabled"]),
        capacity_price_per_user=int(capacity["price_per_user"]),
        buttons=PanelResellerButtons(**panel_reseller_button_settings(panel)),
    )


@router.post("/panel/resellers/settings", response_model=PanelResellerSettingsResponse)
async def read_reseller_settings(payload: PanelRequest, request: Request) -> PanelResellerSettingsResponse:
    async def handle(_: PanelActor) -> PanelResellerSettingsResponse:
        setting = await SettingsManager().get_settings()
        panels = await queries.list_panels()
        return PanelResellerSettingsResponse(
            settings=_global_settings(setting),
            panels=[_panel_settings(panel) for panel in panels],
        )

    return await guard.run(payload, request, PanelResellerSettingsResponse, handle)


@router.post("/panel/resellers/settings/save", response_model=ActionResponse)
async def save_reseller_settings(payload: PanelResellerSettingsSaveRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        if payload.panels:
            known = {int(panel.code): panel for panel in await queries.list_panels()}
            missing = [item.code for item in payload.panels if item.code not in known]
            if missing:
                return ActionResponse(ok=False, error=f"پنل با کد {missing[0]} پیدا نشد.")
            for item in payload.panels:
                if item.capacity_enabled and item.capacity_price_per_user <= 0:
                    return ActionResponse(
                        ok=False, error=f"برای فعال‌کردن خرید ظرفیت در پنل «{item.name or item.code}» قیمت لازم است."
                    )

        if payload.settings is not None:
            updates = {GLOBAL_KEYS[field]: value for field, value in payload.settings.model_dump().items()}
            manager = SettingsManager()
            setting = await manager.get_settings()
            if setting is None:
                await manager.add_setting(**updates)
            else:
                await manager.update_setting(setting.id, **updates)
            await audit.record(
                actor_id=actor.user_id,
                actor_username=actor.username,
                action="reseller_settings_update",
                target_type="settings",
                detail=updates,
                ip=actor.ip,
            )

        for item in payload.panels or []:
            feature = apply_feature_settings_patch(
                known[item.code],
                sales={"reseller_enabled": item.sale_enabled},
                reseller_capacity={"enabled": item.capacity_enabled, "price_per_user": item.capacity_price_per_user},
                reseller_buttons=item.buttons.model_dump(),
            )
            await mutations.upsert_panel(actor, item.code, {"feature_settings": feature})

        if payload.settings is None and not payload.panels:
            return ActionResponse(message="تغییری برای ذخیره وجود نداشت.")
        return ActionResponse(message="تنظیمات نمایندگی ذخیره شد.")

    return await guard.run(payload, request, ActionResponse, handle)
