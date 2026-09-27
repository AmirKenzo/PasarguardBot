"""Admin panel API: installable-webapp (PWA) branding — name, description, icon."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, Request, UploadFile

from app.db.crud.settings import SettingsManager
from app.models.panel.common import ActionResponse, PanelRequest
from app.models.panel.pwa import PwaIconUploadResponse, PwaSettingsResponse, PwaSettingsSaveRequest
from app.panel import audit
from app.routers.panel import guard
from app.routers.panel.auth import PanelActor
from app.services.pwa_icons import MAX_UPLOAD_BYTES, has_custom_icon, save_icon

router = APIRouter()


@router.post("/panel/pwa", response_model=PwaSettingsResponse)
async def read_pwa_settings(payload: PanelRequest, request: Request) -> PwaSettingsResponse:
    async def handle(_: PanelActor) -> PwaSettingsResponse:
        setting = await SettingsManager().get_settings()
        return PwaSettingsResponse(
            app_name=(getattr(setting, "pwa_app_name", None) or "") if setting else "",
            short_name=(getattr(setting, "pwa_short_name", None) or "") if setting else "",
            description=(getattr(setting, "pwa_description", None) or "") if setting else "",
            has_custom_icon=has_custom_icon(),
            icon_version=int(getattr(setting, "pwa_icon_updated_at", 0) or 0) if setting else 0,
        )

    return await guard.run(payload, request, PwaSettingsResponse, handle)


@router.post("/panel/pwa/save", response_model=ActionResponse)
async def save_pwa_settings(payload: PwaSettingsSaveRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        manager = SettingsManager()
        setting = await manager.get_settings()
        updates = {
            "pwa_app_name": payload.app_name.strip() or "PasarguardBot WebApp",
            "pwa_short_name": payload.short_name.strip() or "PasarguardBot",
            "pwa_description": payload.description.strip(),
        }
        if setting is None:
            await manager.add_setting(**updates)
        else:
            await manager.update_setting(setting.id, **updates)

        await audit.record(
            actor_id=actor.user_id,
            actor_username=actor.username,
            action="pwa_settings_update",
            target_type="settings",
            detail={"keys": sorted(updates)},
            ip=actor.ip,
        )
        return ActionResponse(message="تنظیمات PWA ذخیره شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/pwa/icon", response_model=PwaIconUploadResponse)
async def upload_pwa_icon(
    request: Request,
    file: UploadFile = File(...),
    session_token: str | None = Form(None),
    init_data: str | None = Form(None),
) -> PwaIconUploadResponse:
    payload = PanelRequest(session_token=session_token, init_data=init_data)

    async def handle(actor: PanelActor) -> PwaIconUploadResponse:
        if not (file.content_type or "").startswith("image/"):
            return PwaIconUploadResponse(ok=False, error="فایل باید یک تصویر باشد.")

        content = await file.read()
        if len(content) > MAX_UPLOAD_BYTES:
            return PwaIconUploadResponse(ok=False, error="حجم تصویر نباید بیشتر از ۵ مگابایت باشد.")

        try:
            save_icon(content)
        except Exception:
            return PwaIconUploadResponse(ok=False, error="تصویر نامعتبر است.")

        manager = SettingsManager()
        setting = await manager.get_settings()
        icon_version = int(getattr(setting, "pwa_icon_updated_at", 0) or 0) + 1 if setting else 1
        if setting is None:
            await manager.add_setting(pwa_icon_updated_at=icon_version)
        else:
            await manager.update_setting(setting.id, pwa_icon_updated_at=icon_version)

        await audit.record(
            actor_id=actor.user_id,
            actor_username=actor.username,
            action="pwa_icon_update",
            target_type="settings",
            detail={"icon_version": icon_version},
            ip=actor.ip,
        )
        return PwaIconUploadResponse(message="آیکن PWA به‌روزرسانی شد.", icon_version=icon_version)

    return await guard.run(payload, request, PwaIconUploadResponse, handle)
