"""Connected PasarGuard panels: list, add, edit, test connection, delete.

Credentials are stored the way the bot stores them: the password encrypted
with ``encrypt_data`` and ``cookie`` holding the access token or the API key.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.db.crud.panels import PanelsManager
from app.logger import get_logger
from app.models.panel.common import ActionResponse, PanelRequest
from app.models.panel.panels import (
    AUTH_TYPES,
    PanelCodeRequest,
    PanelListResponse,
    PanelRow,
    PanelSaveRequest,
)
from app.panel import audit, mutations, queries
from app.routers.panel import guard
from app.routers.panel.auth import PanelActor
from app.services.panels.auth import (
    AUTH_API_KEY,
    PANEL_AUTH_PLACEHOLDER_USERNAME,
    fetch_panel_groups_with_auth,
    verify_panel_api_key,
    verify_panel_password,
)
from app.services.panels.settings import panel_test_duration_days, panel_test_flag, panel_test_volume_gb
from app.utils.security.crypto import encrypt_data

log = get_logger(__name__)
router = APIRouter()


async def _verify(base_url: str, auth_type: str, username: str, secret: str) -> str | None:
    """Return the cookie/token to store, or ``None`` when the panel refuses."""
    try:
        if auth_type == AUTH_API_KEY:
            await verify_panel_api_key(base_url, secret)
            return secret.strip()
        _api, token, _groups = await verify_panel_password(base_url, username, secret)
        return token
    except Exception as exc:
        log.warning("panel credentials rejected by %s: %s", base_url, exc)
        return None


@router.post("/panel/panels", response_model=PanelListResponse)
async def list_panels(payload: PanelRequest, request: Request) -> PanelListResponse:
    async def handle(_: PanelActor) -> PanelListResponse:
        panels = await queries.list_panels()
        return PanelListResponse(
            panels=[
                PanelRow(
                    code=int(panel.code),
                    name=panel.name,
                    base_url=panel.base_url,
                    tunnel_url=panel.tunnel_url,
                    username=panel.username,
                    auth_type=getattr(panel, "auth_type", "password"),
                    enable=bool(panel.enable),
                    test_enabled=panel_test_flag(panel),
                    test_volume_gb=panel_test_volume_gb(panel),
                    test_duration_days=panel_test_duration_days(panel),
                )
                for panel in panels
            ]
        )

    return await guard.run(payload, request, PanelListResponse, handle)


@router.post("/panel/panels/save", response_model=ActionResponse)
async def save_panel(payload: PanelSaveRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        auth_type = payload.auth_type if payload.auth_type in AUTH_TYPES else "password"
        name = payload.name.strip()[:50]
        base_url = payload.base_url.strip().rstrip("/")[:255]
        username = payload.username.strip()
        secret = payload.secret.strip()
        if not name or not base_url:
            return ActionResponse(ok=False, error="نام و آدرس پنل الزامی است.")

        if payload.code is None:
            if not secret:
                return ActionResponse(ok=False, error="رمز عبور یا API Key الزامی است.")
            cookie = await _verify(base_url, auth_type, username, secret)
            if cookie is None:
                return ActionResponse(ok=False, error="اتصال به پنل با این مشخصات برقرار نشد.")
            panels = await queries.list_panels()
            new_code = max((int(item.code) for item in panels), default=0) + 1
            await PanelsManager().add_panel(
                code=new_code,
                name=name,
                enable=payload.enable,
                base_url=base_url,
                username=(username or PANEL_AUTH_PLACEHOLDER_USERNAME)[:50],
                password=encrypt_data(secret),
                cookie=cookie,
                tunnel_url=(payload.tunnel_url.strip() or None),
                auth_type=auth_type,
            )
            await PanelsManager().update_panel(
                code=new_code,
                test_enabled=payload.test_enabled,
                test_volume_gb=payload.test_volume_gb,
                test_duration_days=payload.test_duration_days,
            )
            await audit.record(
                actor_id=actor.user_id,
                actor_username=actor.username,
                action="panel_create",
                target_type="panel",
                target_id=new_code,
                detail={"name": name, "base_url": base_url, "auth_type": auth_type},
                ip=actor.ip,
            )
            return ActionResponse(message="پنل اضافه شد.")

        panel = await queries.get_panel(payload.code)
        if panel is None:
            return ActionResponse(ok=False, error="پنلی با این کد پیدا نشد.")

        values: dict = {
            "name": name,
            "base_url": base_url,
            "tunnel_url": payload.tunnel_url.strip() or None,
            "enable": payload.enable,
            "auth_type": auth_type,
            "username": (username or panel.username or PANEL_AUTH_PLACEHOLDER_USERNAME)[:50],
            "test_enabled": payload.test_enabled,
            "test_volume_gb": payload.test_volume_gb,
            "test_duration_days": payload.test_duration_days,
        }
        if secret:
            cookie = await _verify(base_url, auth_type, values["username"], secret)
            if cookie is None:
                return ActionResponse(ok=False, error="اتصال به پنل با این مشخصات برقرار نشد.")
            values["password"] = encrypt_data(secret)
            values["cookie"] = cookie

        await mutations.upsert_panel(actor, payload.code, values)
        return ActionResponse(message="پنل به‌روزرسانی شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/panels/test", response_model=ActionResponse)
async def test_panel(payload: PanelCodeRequest, request: Request) -> ActionResponse:
    async def handle(_: PanelActor) -> ActionResponse:
        panel = await queries.get_panel(payload.code)
        if panel is None:
            return ActionResponse(ok=False, error="پنلی با این کد پیدا نشد.")
        try:
            await fetch_panel_groups_with_auth(panel)
        except Exception as exc:
            log.warning("panel %s connection test failed: %s", payload.code, exc)
            return ActionResponse(ok=False, error="اتصال به پنل برقرار نشد.")
        return ActionResponse(message="اتصال به پنل سالم است.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/panels/delete", response_model=ActionResponse)
async def delete_panel(payload: PanelCodeRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        ok = await mutations.delete_panel(actor, payload.code)
        if not ok:
            return ActionResponse(ok=False, error="پنلی با این کد پیدا نشد.")
        return ActionResponse(message="پنل حذف شد. سرویس‌های ثبت‌شده روی آن بدون پنل می‌مانند.")

    return await guard.run(payload, request, ActionResponse, handle)
