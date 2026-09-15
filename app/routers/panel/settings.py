"""Bot settings, built from the section defaults in ``app.db.models.settings``."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from app.db.crud.settings import SettingsManager
from app.db.models.settings import SETTINGS_SECTION_DEFAULTS
from app.models.panel.common import ActionResponse, PanelRequest
from app.models.panel.settings import (
    PanelSettingField,
    PanelSettingSection,
    PanelSettingsResponse,
    PanelSettingsSaveRequest,
)
from app.panel import audit
from app.routers.panel import guard
from app.routers.panel.auth import PanelActor
from app.services.keyboard_glass import apply_glass_mode, glass_mode_active

router = APIRouter()


def _current(setting: Any, section: str, key: str, default: Any) -> Any:
    if setting is None:
        return default
    data = getattr(setting, section, None)
    if isinstance(data, dict) and key in data:
        return data[key]
    return default


def _field_type(default: Any) -> str:
    if isinstance(default, bool):
        return "bool"
    return "text" if isinstance(default, str) else "number"


def _coerce(raw: Any, default: Any) -> Any:
    """Cast one submitted value to the shape the stored default implies."""
    if isinstance(default, bool):
        return bool(raw)
    if isinstance(default, str):
        # A cleared text field means "off", not "restore the default".
        return "" if raw is None else str(raw).strip()
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None if default is None else default
    number = float(str(raw).replace(",", "").strip())
    return int(number) if number.is_integer() else number


@router.post("/panel/settings", response_model=PanelSettingsResponse)
async def read_settings(payload: PanelRequest, request: Request) -> PanelSettingsResponse:
    async def handle(_: PanelActor) -> PanelSettingsResponse:
        setting = await SettingsManager().get_settings()
        return PanelSettingsResponse(
            initialized=setting is not None,
            sections=[
                PanelSettingSection(
                    key=section,
                    fields=[
                        PanelSettingField(
                            key=key,
                            type=_field_type(default),
                            default=default,
                            value=_current(setting, section, key, default),
                        )
                        for key, default in defaults.items()
                    ],
                )
                for section, defaults in SETTINGS_SECTION_DEFAULTS.items()
            ],
        )

    return await guard.run(payload, request, PanelSettingsResponse, handle)


@router.post("/panel/settings/save", response_model=ActionResponse)
async def save_settings(payload: PanelSettingsSaveRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        manager = SettingsManager()
        setting = await manager.get_settings()

        updates: dict[str, Any] = {}
        for defaults in SETTINGS_SECTION_DEFAULTS.values():
            for key, default in defaults.items():
                if isinstance(default, bool):
                    updates[key] = bool(payload.values.get(key, False))
                    continue
                if key not in payload.values:
                    continue
                try:
                    updates[key] = _coerce(payload.values[key], default)
                except ValueError:
                    return ActionResponse(ok=False, error=f"مقدار «{key}» عددی نیست.")

        glass_before = glass_mode_active(setting)
        if setting is None:
            await manager.add_setting(**updates)
        else:
            await manager.update_setting(setting.id, **updates)

        # The glassy look is baked into the stored button labels, so flipping the
        # switch has to rewrite them; nothing else here has work to do after the save.
        glass_after = bool(updates.get("glass_buttons_mode", glass_before))
        if glass_after != glass_before:
            await apply_glass_mode(glass_after)

        await audit.record(
            admin_id=actor.user_id,
            admin_username=actor.username,
            action="settings_update",
            target_type="settings",
            detail={"keys": sorted(updates)},
            ip=actor.ip,
        )
        return ActionResponse(message="تنظیمات ذخیره شد.")

    return await guard.run(payload, request, ActionResponse, handle)
