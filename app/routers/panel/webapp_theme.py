"""Web app color themes: pick, edit and share the colors every user sees in the web app."""

from __future__ import annotations

import io
import json

from fastapi import APIRouter, Request

from app import Kenzo
from app.logger import get_logger
from app.models.panel.common import ActionResponse, PanelRequest
from app.models.panel.webapp_theme import (
    WebappThemeActivateRequest,
    WebappThemeIdRequest,
    WebappThemeOptionsRequest,
    WebappThemeOverviewResponse,
    WebappThemeSaveRequest,
    WebappThemeSaveResponse,
    WebappThemeShareResponse,
)
from app.panel import audit
from app.routers.panel import guard
from app.routers.panel.auth import PanelActor
from app.services import webapp_theme

router = APIRouter()
log = get_logger(__name__)


async def _log(actor: PanelActor, action: str, **kwargs) -> None:
    await audit.record(actor_id=actor.user_id, actor_username=actor.username, action=action, ip=actor.ip, **kwargs)


@router.post("/panel/webapp-themes", response_model=WebappThemeOverviewResponse)
async def overview(payload: PanelRequest, request: Request) -> WebappThemeOverviewResponse:
    async def handle(_: PanelActor) -> WebappThemeOverviewResponse:
        config = await webapp_theme.get_config()
        return WebappThemeOverviewResponse(
            mode=config["mode"],
            active=config["active"],
            user_scheme=config["user_scheme"],
            user_pick=config["user_pick"],
            themes=await webapp_theme.list_themes(),
            max_themes=webapp_theme.MAX_LIBRARY_THEMES,
        )

    return await guard.run(payload, request, WebappThemeOverviewResponse, handle)


@router.post("/panel/webapp-themes/save", response_model=WebappThemeSaveResponse)
async def save_theme(payload: WebappThemeSaveRequest, request: Request) -> WebappThemeSaveResponse:
    async def handle(actor: PanelActor) -> WebappThemeSaveResponse:
        try:
            theme_id = await webapp_theme.save_theme(
                payload.theme,
                name=payload.name,
                theme_id=payload.theme_id,
                actor_id=actor.user_id,
                source_bot=payload.source_bot,
                imported=payload.imported,
            )
        except webapp_theme.ThemeError as exc:
            return WebappThemeSaveResponse(ok=False, error=webapp_theme.error_text(exc.code))
        action = "webapp_theme_update" if payload.theme_id else "webapp_theme_create"
        await _log(actor, action, target_type="webapp_theme", target_id=theme_id, detail={"imported": payload.imported})
        return WebappThemeSaveResponse(message="تم ذخیره شد.", theme_id=theme_id)

    return await guard.run(payload, request, WebappThemeSaveResponse, handle)


@router.post("/panel/webapp-themes/delete", response_model=ActionResponse)
async def delete_theme(payload: WebappThemeIdRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        if not await webapp_theme.delete_theme(payload.theme_id):
            return ActionResponse(ok=False, error=webapp_theme.error_text("not_found"))
        await _log(actor, "webapp_theme_delete", target_type="webapp_theme", target_id=payload.theme_id)
        return ActionResponse(message="تم حذف شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/webapp-themes/activate", response_model=ActionResponse)
async def activate(payload: WebappThemeActivateRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        try:
            await webapp_theme.activate(payload.active, payload.theme)
        except webapp_theme.ThemeError as exc:
            return ActionResponse(ok=False, error=webapp_theme.error_text(exc.code))
        await _log(actor, "webapp_theme_activate", target_type="webapp_theme", detail={"active": payload.active})
        return ActionResponse(message="تم برای همه کاربران فعال شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/webapp-themes/options", response_model=ActionResponse)
async def update_options(payload: WebappThemeOptionsRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        try:
            await webapp_theme.update_options(
                mode=payload.mode, user_scheme=payload.user_scheme, user_pick=payload.user_pick
            )
        except webapp_theme.ThemeError as exc:
            return ActionResponse(ok=False, error=webapp_theme.error_text(exc.code))
        detail = payload.model_dump(include={"mode", "user_scheme", "user_pick"})
        await _log(actor, "webapp_theme_options", target_type="settings", detail=detail)
        return ActionResponse(message="تنظیمات ظاهر وب‌اپ ذخیره شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/webapp-themes/share", response_model=WebappThemeShareResponse)
async def share(payload: WebappThemeIdRequest, request: Request) -> WebappThemeShareResponse:
    async def handle(_: PanelActor) -> WebappThemeShareResponse:
        entry = await webapp_theme.get_theme(payload.theme_id)
        if entry is None:
            return WebappThemeShareResponse(ok=False, error=webapp_theme.error_text("not_found"))
        return WebappThemeShareResponse(
            data=webapp_theme.share_pack(entry), file_name=webapp_theme.share_file_name(entry["name"])
        )

    return await guard.run(payload, request, WebappThemeShareResponse, handle)


@router.post("/panel/webapp-themes/send", response_model=ActionResponse)
async def send(payload: WebappThemeIdRequest, request: Request) -> ActionResponse:
    """Send a library theme as a file to the admin's private chat, ready to forward to someone."""

    async def handle(actor: PanelActor) -> ActionResponse:
        entry = await webapp_theme.get_theme(payload.theme_id)
        if entry is None:
            return ActionResponse(ok=False, error=webapp_theme.error_text("not_found"))
        if not Kenzo.is_connected():
            return ActionResponse(ok=False, error="ربات به تلگرام متصل نیست.")
        body = json.dumps(webapp_theme.share_pack(entry), ensure_ascii=False, indent=2)
        document = io.BytesIO(body.encode("utf-8"))
        document.name = webapp_theme.share_file_name(entry["name"])
        try:
            await Kenzo.send_file(
                actor.user_id, document, caption=webapp_theme.share_caption(entry), force_document=True
            )
        except Exception as exc:
            log.error("panel: webapp theme delivery failed: %s", exc, exc_info=True)
            return ActionResponse(ok=False, error="ارسال فایل تم انجام نشد.")
        await _log(actor, "webapp_theme_send", target_type="webapp_theme", target_id=payload.theme_id)
        return ActionResponse(message="فایل تم در چت خصوصی ربات برایت ارسال شد.")

    return await guard.run(payload, request, ActionResponse, handle)
