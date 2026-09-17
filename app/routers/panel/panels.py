"""Connected PasarGuard panels: list, add, edit, test connection, delete.

Credentials are stored the way the bot stores them: the password encrypted
with ``encrypt_data`` and ``cookie`` holding the access token or the API key.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Request

from app.db.crud.keyboards import KeyboardButtonCRUD
from app.db.crud.panels import PanelsManager
from app.logger import get_logger
from app.models.panel.common import ActionResponse, PanelRequest, page_meta
from app.models.panel.panel_options import (
    DEFAULT_PANEL_OPTION_FIELDS,
    PANEL_OPTION_FIELDS,
    PanelOptionRow,
    PanelOptionsRequest,
    PanelOptionsResponse,
)
from app.models.panel.panels import (
    AUTH_TYPES,
    BUTTON_STYLES,
    PanelButtonSettingsPayload,
    PanelButtonStyleResponse,
    PanelButtonStyleSaveRequest,
    PanelCodeRequest,
    PanelCustomBuySettingsPayload,
    PanelGroupOption,
    PanelGroupsResponse,
    PanelListResponse,
    PanelRenewalSettingsPayload,
    PanelResellerButtonSettingsPayload,
    PanelResellerCapacitySettingsPayload,
    PanelRow,
    PanelSalesSettingsPayload,
    PanelSaveRequest,
    PanelSettingsResponse,
    PanelSettingsSaveRequest,
    PanelStatusResponse,
    PanelSubscriptionSettingsPayload,
    PanelTestResponse,
    PanelTrialSettingsPayload,
)
from app.panel import audit, mutations, queries
from app.routers.panel import guard
from app.routers.panel.auth import PanelActor
from app.services.panels.auth import (
    AUTH_API_KEY,
    PANEL_AUTH_PLACEHOLDER_USERNAME,
    create_panel_api,
    fetch_panel_groups_with_auth,
    panel_uses_api_key,
    refresh_panel_cookie,
    verify_panel_api_key,
    verify_panel_password,
)
from app.services.panels.settings import (
    apply_feature_settings_patch,
    button_settings,
    panel_admin_login_path,
    panel_custom_buy_settings,
    panel_default_group_ids,
    panel_display_mode,
    panel_node_prefixes,
    panel_reseller_button_settings,
    panel_reseller_capacity_settings,
    panel_reseller_sale_flag,
    panel_sales_settings,
    panel_shop_sale_flag,
    panel_show_prefixes_in_locations,
    panel_single_config_link_indexes,
    panel_subscription_link_mode,
    panel_test_duration_days,
    panel_test_flag,
    panel_test_volume_gb,
    panel_user_limit,
    renewal_settings,
)
from app.telegram.shared.keyboards.panel_buttons import panel_display_keyboard_key
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


@router.post("/panel/panels/options", response_model=PanelOptionsResponse)
async def panel_options(payload: PanelOptionsRequest, request: Request) -> PanelOptionsResponse:

    async def handle(_: PanelActor) -> PanelOptionsResponse:
        fields = [f for f in dict.fromkeys(payload.fields) if f in PANEL_OPTION_FIELDS] or list(
            DEFAULT_PANEL_OPTION_FIELDS
        )
        rows, total = await queries.list_panel_options(
            fields=tuple(fields), q=payload.q.strip(), page=payload.page, per_page=payload.limit
        )
        return PanelOptionsResponse(
            panels=[PanelOptionRow(**dict(zip(fields, row, strict=True))) for row in rows],
            meta=page_meta(total, payload.page, payload.limit),
        )

    return await guard.run(payload, request, PanelOptionsResponse, handle)


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


@router.post("/panel/panels/test", response_model=PanelTestResponse)
async def test_panel(payload: PanelCodeRequest, request: Request) -> PanelTestResponse:
    async def handle(_: PanelActor) -> PanelTestResponse:
        panel = await queries.get_panel(payload.code)
        if panel is None:
            return PanelTestResponse(ok=False, error="پنلی با این کد پیدا نشد.")
        started = time.perf_counter()
        try:
            await fetch_panel_groups_with_auth(panel)
        except Exception as exc:
            log.warning("panel %s connection test failed: %s", payload.code, exc)
            return PanelTestResponse(ok=False, error="اتصال به پنل برقرار نشد.")
        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        return PanelTestResponse(message="اتصال به پنل سالم است.", latency_ms=latency_ms)

    return await guard.run(payload, request, PanelTestResponse, handle)


@router.post("/panel/panels/delete", response_model=ActionResponse)
async def delete_panel(payload: PanelCodeRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        ok = await mutations.delete_panel(actor, payload.code)
        if not ok:
            return ActionResponse(ok=False, error="پنلی با این کد پیدا نشد.")
        return ActionResponse(message="پنل حذف شد. سرویس‌های ثبت‌شده روی آن بدون پنل می‌مانند.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/panels/settings", response_model=PanelSettingsResponse)
async def get_panel_settings(payload: PanelCodeRequest, request: Request) -> PanelSettingsResponse:
    async def handle(_: PanelActor) -> PanelSettingsResponse:
        panel = await queries.get_panel(payload.code)
        if panel is None:
            return PanelSettingsResponse(ok=False, error="پنلی با این کد پیدا نشد.", code=payload.code)

        return PanelSettingsResponse(
            code=payload.code,
            buttons=PanelButtonSettingsPayload(**button_settings(panel)),
            subscription=PanelSubscriptionSettingsPayload(
                default_group_ids=panel_default_group_ids(panel),
                user_limit=panel_user_limit(panel),
                display_mode=panel_display_mode(panel),
                node_prefixes=panel_node_prefixes(panel),
                show_prefixes_in_locations=panel_show_prefixes_in_locations(panel),
                link_mode=panel_subscription_link_mode(panel),
                single_config_link_indexes=panel_single_config_link_indexes(panel),
                admin_login_path=panel_admin_login_path(panel),
            ),
            trial=PanelTrialSettingsPayload(
                enabled=panel_test_flag(panel),
                volume_gb=panel_test_volume_gb(panel),
                duration_days=panel_test_duration_days(panel),
            ),
            renewal=PanelRenewalSettingsPayload(**renewal_settings(panel)),
            sales=PanelSalesSettingsPayload(**panel_sales_settings(panel)),
            custom_buy=PanelCustomBuySettingsPayload(**panel_custom_buy_settings(panel)),
            reseller_capacity=PanelResellerCapacitySettingsPayload(**panel_reseller_capacity_settings(panel)),
            reseller_buttons=PanelResellerButtonSettingsPayload(**panel_reseller_button_settings(panel)),
        )

    return await guard.run(payload, request, PanelSettingsResponse, handle)


@router.post("/panel/panels/settings/save", response_model=ActionResponse)
async def save_panel_settings(payload: PanelSettingsSaveRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        panel = await queries.get_panel(payload.code)
        if panel is None:
            return ActionResponse(ok=False, error="پنلی با این کد پیدا نشد.")

        values: dict = {}
        if payload.buttons is not None:
            values["button_settings"] = payload.buttons.model_dump(exclude_none=True)
        if payload.subscription is not None:
            values["subscription_settings"] = payload.subscription.model_dump(exclude_none=True)
        if payload.trial is not None:
            values["test_settings"] = payload.trial.model_dump(exclude_none=True)
        if payload.renewal is not None:
            values["renewal_settings"] = payload.renewal.model_dump(exclude_none=True)

        if payload.sales or payload.custom_buy or payload.reseller_capacity or payload.reseller_buttons:
            values["feature_settings"] = apply_feature_settings_patch(
                panel,
                sales=payload.sales.model_dump(exclude_none=True) if payload.sales else None,
                custom_buy=payload.custom_buy.model_dump(exclude_none=True) if payload.custom_buy else None,
                reseller_capacity=(
                    payload.reseller_capacity.model_dump(exclude_none=True) if payload.reseller_capacity else None
                ),
                reseller_buttons=(
                    payload.reseller_buttons.model_dump(exclude_none=True) if payload.reseller_buttons else None
                ),
            )

        if not values:
            return ActionResponse(message="تغییری برای ذخیره وجود نداشت.")

        await mutations.upsert_panel(actor, payload.code, values)
        return ActionResponse(message="تنظیمات پنل ذخیره شد.")

    return await guard.run(payload, request, ActionResponse, handle)


@router.post("/panel/panels/status", response_model=PanelStatusResponse)
async def get_panel_status(payload: PanelCodeRequest, request: Request) -> PanelStatusResponse:
    async def handle(_: PanelActor) -> PanelStatusResponse:
        panel = await queries.get_panel(payload.code)
        if panel is None:
            return PanelStatusResponse(ok=False, error="پنلی با این کد پیدا نشد.", code=payload.code)

        result = PanelStatusResponse(
            code=int(panel.code),
            name=panel.name,
            enable=bool(panel.enable),
            shop_enabled=panel_shop_sale_flag(panel),
            reseller_enabled=panel_reseller_sale_flag(panel),
            auth_type=getattr(panel, "auth_type", "password"),
            base_url=panel.base_url,
            tunnel_url=panel.tunnel_url,
        )

        async def fetch_stats() -> None:
            api = create_panel_api(panel)
            kwargs = {} if panel_uses_api_key(panel) else {"admin_username": panel.username}
            stats = await api.get_system_stats(**kwargs)
            result.version = stats.version
            result.mem_total = stats.mem_total
            result.mem_used = stats.mem_used
            result.cpu_cores = stats.cpu_cores
            result.cpu_usage = stats.cpu_usage
            result.total_user = stats.total_user
            result.online_users = stats.online_users
            result.active_users = stats.active_users
            result.on_hold_users = stats.on_hold_users
            result.disabled_users = stats.disabled_users
            result.expired_users = stats.expired_users
            result.limited_users = stats.limited_users
            result.incoming_bandwidth = stats.incoming_bandwidth
            result.outgoing_bandwidth = stats.outgoing_bandwidth

        try:
            await fetch_stats()
        except Exception as exc:
            message = str(exc)
            if "401" in message and not panel_uses_api_key(panel):
                try:
                    await refresh_panel_cookie(panel)
                    await fetch_stats()
                except Exception as exc2:
                    result.status_error = f"خطا در دریافت وضعیت سرور: {exc2}"
            else:
                result.status_error = f"خطا در دریافت وضعیت سرور: {message}"

        return result

    return await guard.run(payload, request, PanelStatusResponse, handle)


@router.post("/panel/panels/groups", response_model=PanelGroupsResponse)
async def get_panel_groups(payload: PanelCodeRequest, request: Request) -> PanelGroupsResponse:
    async def handle(_: PanelActor) -> PanelGroupsResponse:
        panel = await queries.get_panel(payload.code)
        if panel is None:
            return PanelGroupsResponse(ok=False, error="پنلی با این کد پیدا نشد.")
        try:
            groups_resp = await fetch_panel_groups_with_auth(panel)
        except Exception as exc:
            log.warning("panel %s groups fetch failed: %s", payload.code, exc)
            return PanelGroupsResponse(ok=False, error="دریافت گروه‌ها از پنل ناموفق بود.")
        return PanelGroupsResponse(
            groups=[PanelGroupOption(id=group.id, name=group.name) for group in groups_resp.groups]
        )

    return await guard.run(payload, request, PanelGroupsResponse, handle)


@router.post("/panel/panels/button-style", response_model=PanelButtonStyleResponse)
async def get_panel_button_style(payload: PanelCodeRequest, request: Request) -> PanelButtonStyleResponse:
    async def handle(_: PanelActor) -> PanelButtonStyleResponse:
        panel = await queries.get_panel(payload.code)
        if panel is None:
            return PanelButtonStyleResponse(ok=False, error="پنلی با این کد پیدا نشد.")
        button = await KeyboardButtonCRUD().get_button(panel_display_keyboard_key(payload.code))
        icon_id = button.button_icon if button else None
        return PanelButtonStyleResponse(
            text=(button.button_text or "") if button else "",
            style=(button.button_style or "") if button else "",
            icon_id=str(icon_id) if icon_id is not None else None,
        )

    return await guard.run(payload, request, PanelButtonStyleResponse, handle)


@router.post("/panel/panels/button-style/save", response_model=ActionResponse)
async def save_panel_button_style(payload: PanelButtonStyleSaveRequest, request: Request) -> ActionResponse:
    async def handle(_: PanelActor) -> ActionResponse:
        panel = await queries.get_panel(payload.code)
        if panel is None:
            return ActionResponse(ok=False, error="پنلی با این کد پیدا نشد.")
        if payload.style is not None and payload.style not in BUTTON_STYLES:
            return ActionResponse(ok=False, error="رنگ دکمه نامعتبر است.")

        icon_id_value: int | None = None
        if payload.icon_id is not None:
            cleaned = payload.icon_id.strip()
            if cleaned and not cleaned.isdigit():
                return ActionResponse(ok=False, error="شناسه آیکون باید فقط عدد باشد.")
            icon_id_value = int(cleaned) if cleaned else None

        ok = await KeyboardButtonCRUD().set_button(
            panel_display_keyboard_key(payload.code),
            button_text=(payload.text.strip() if payload.text is not None else None),
            button_style=payload.style,
            button_icon=icon_id_value,
            clear_icon=payload.clear_icon,
        )
        if not ok:
            return ActionResponse(ok=False, error="ذخیره استایل دکمه ناموفق بود.")
        return ActionResponse(message="استایل دکمه ذخیره شد.")

    return await guard.run(payload, request, ActionResponse, handle)
