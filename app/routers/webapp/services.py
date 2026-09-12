"""Service list/detail, config links, connected clients, link/subscription change."""

from datetime import UTC, datetime
from time import time as unix_time
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter
from pasarguard import PasarguardAPI, ProxySettings, UserModify

from app.db.crud.panels import PanelsManager
from app.db.crud.services import ServiceCRUD, get_user_service_panel_counts, get_user_services_paginated
from app.db.crud.settings import SettingsManager
from app.logger import get_logger
from app.models.webapp import (
    PanelGroupItem,
    ServiceButtons,
    WebAppChangeLinkRequest,
    WebAppChangeResponse,
    WebAppChangeSubscriptionRequest,
    WebAppClientItem,
    WebAppClientsRequest,
    WebAppClientsResponse,
    WebAppConfigLinkItem,
    WebAppConfigLinksRequest,
    WebAppConfigLinksResponse,
    WebAppServiceDetailRequest,
    WebAppServiceDetailResponse,
    WebAppServicesRequest,
    WebAppServicesResponse,
)
from app.routers.webapp.auth import authenticate_user
from app.services.billing.renewal import require_panel_userid
from app.services.panels.config_links import (
    config_link_display_name,
    fetch_service_config_links,
    fetch_user_config_links,
)
from app.services.panels.settings import panel_button_enabled
from app.utils.formatting.dates import Time_Date, relative_time, timestamp_to_persian_expiry
from app.utils.formatting.traffic import format_ip_limit, format_size

logger = get_logger(__name__)
router = APIRouter()

# Status texts with clean emojis
STATUS_TEXTS = {
    "active": "فعال",
    "expired": "منقضی شده",
    "limited": "محدود (حجم تمام شده)",
    "disabled": "غیرفعال",
    "on_hold": "در انتظار",
}
STATUS_EMOJI = {"active": "✅", "expired": "🕔", "limited": "🪫", "disabled": "❌", "on_hold": "🔋"}

RESET_STRATEGY_LABELS = {"day": "روزانه", "week": "هفتگی", "month": "ماهانه", "year": "سالانه"}
RESET_STRATEGY_DIVISORS = {"day": 1, "week": 7, "month": 30, "year": 365}


def _compute_reset_info(service: Any, user: Any, total_traffic_bytes: int) -> tuple[str | None, str | None]:
    """Mirrors the reset-cycle math in app/telegram/user/services/helpers.py so the
    webapp shows the same numbers as the bot's service info message."""

    strategy = getattr(service, "data_limit_reset_strategy", None) or "no_reset"
    label = RESET_STRATEGY_LABELS.get(strategy)
    expire = getattr(user, "expire", None)
    if not label or not expire or total_traffic_bytes <= 0:
        return None, None

    now = datetime.now(UTC) if expire.tzinfo is not None else datetime.now()
    remaining_days = max((expire - now).days, 0)
    periods = remaining_days // RESET_STRATEGY_DIVISORS[strategy]
    total_possible_bytes = total_traffic_bytes * periods
    return label, format_size(total_possible_bytes, decimal_places=1)


async def _process_services_from_db(user_services: list[Any], hide_panel_name: bool = False) -> list[dict[str, Any]]:
    """Build service list from DB only. No Marzban API calls."""

    panels_by_code = {panel.code: panel for panel in await PanelsManager().get_all_panels()}
    now = int(unix_time())

    result = []
    for service in user_services:
        panel = panels_by_code.get(service.in_panel) if service.in_panel else None
        panel_name = None if hide_panel_name else (panel.name if panel else None)

        exp_ts = getattr(service, "expiration_time", None)
        status = "expired" if exp_ts is not None and exp_ts < now else "active"

        pkg = getattr(service, "package_size", None) or 0
        total_traffic_str = format_size(pkg, decimal_places=0) if pkg else "0 B"

        exp_str = timestamp_to_persian_expiry(exp_ts) if exp_ts else "نامشخص"

        txt = STATUS_TEXTS.get(status, "نامشخص")
        emoji = STATUS_EMOJI.get(status, "")
        result.append(
            {
                "code": str(service.code),
                "username": service.username,
                "panel_name": panel_name,
                "status": status,
                "status_text": f"{emoji} {txt}".strip() if emoji else txt,
                "used_traffic": "—",
                "remaining_traffic": "—",
                "total_traffic": total_traffic_str,
                "used_traffic_bytes": 0,
                "remaining_traffic_bytes": 0,
                "total_traffic_bytes": int(pkg) if pkg else 0,
                "expiration_time": exp_str,
                "subscription_url": "",
                "is_test": bool(getattr(service, "is_test", False)),
            }
        )
    return result


async def build_services_payload(
    user_id: int,
    page: int = 1,
    limit: int = 10,
    search: str | None = None,
    panel_code: int | None = None,
) -> dict[str, Any]:
    """Build paginated services payload from DB only (fast, no Marzban calls).

    When panel grouping is enabled and no panel is selected, returns a list of
    the user's panels with per-panel service counts instead of a flat service list.
    """

    settings = await SettingsManager().get_settings()
    grouping_enabled = bool(getattr(settings, "panel_grouping_mode", False)) if settings else False

    if grouping_enabled and panel_code is None:
        panel_counts = await get_user_service_panel_counts(user_id)
        panels_by_code = {panel.code: panel for panel in await PanelsManager().get_all_panels()}
        panel_groups = [
            PanelGroupItem(
                panel_code=code,
                panel_name=panels_by_code[code].name if code in panels_by_code else "پنل حذف‌شده",
                service_count=count,
            )
            for code, count in panel_counts
        ]
        panel_groups.sort(key=lambda g: g.service_count, reverse=True)
        return {
            "ok": True,
            "services": None,
            "total": sum(g.service_count for g in panel_groups),
            "page": 1,
            "limit": limit,
            "total_pages": 1,
            "grouping_enabled": True,
            "panel_groups": panel_groups,
        }

    user_services, total = await get_user_services_paginated(
        user_id, page=page, limit=limit, search=search, panel_code=panel_code
    )
    services_data = await _process_services_from_db(user_services, hide_panel_name=grouping_enabled)
    total_pages = (total + limit - 1) // limit if limit > 0 else 0
    return {
        "ok": True,
        "services": services_data,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
        "grouping_enabled": grouping_enabled,
        "panel_groups": None,
    }


async def _build_service_detail(service: Any, panel: Any) -> dict[str, Any]:
    """Build full service detail from Marzban (called when user clicks on service)."""

    status_messages = {
        "active": "فعال",
        "expired": "منقضی شده (تاریخ اکانت تمام شده)",
        "limited": "محدود (حجم تمام شده)",
        "disabled": "غیرفعال",
        "on_hold": "در انتظار (زمان کانفیگ بعد از اتصال شروع میشود)",
    }
    fallback = {
        "used_traffic": "0 B",
        "remaining_traffic": "0 B",
        "total_traffic": "0 B",
        "used_traffic_bytes": 0,
        "remaining_traffic_bytes": 0,
        "total_traffic_bytes": 0,
        "expiration_time": "نامشخص",
        "subscription_url": "نامشخص",
        "ip_limit_text": format_ip_limit(getattr(service, "ip_limit", 0)),
        "helper_subscription_url": None,
        "is_test": bool(getattr(service, "is_test", False)),
        "config_value": None,
        "lifetime_used_traffic": None,
        "last_connection": None,
        "last_edit": None,
        "single_config_links": [],
    }

    try:
        marzban_api = PasarguardAPI(panel.base_url)
        user = await marzban_api.get_user_by_id(user_id=require_panel_userid(service), token=panel.cookie)
        if not user or not hasattr(user, "subscription_url"):
            raise ValueError("Marzban user data invalid")

        subscription_url = user.subscription_url
        if subscription_url and not subscription_url.startswith("http"):
            base = (panel.base_url or "").rstrip("/")
            path = subscription_url if subscription_url.startswith("/") else f"/{subscription_url}"
            subscription_url = f"{base}{path}"
        subscription_url = subscription_url or "نامشخص"

        helper_url = None
        if getattr(panel, "tunnel_url", None) and subscription_url != "نامشخص":
            if subscription_url.startswith("http"):
                parsed = urlparse(subscription_url)
                helper_url = f"{panel.tunnel_url.rstrip('/')}{parsed.path or '/'}"
            else:
                path = subscription_url if subscription_url.startswith("/") else f"/{subscription_url}"
                helper_url = f"{panel.tunnel_url.rstrip('/')}{path}"

        used_traffic = getattr(user, "used_traffic", None) or 0
        total_traffic = getattr(user, "data_limit", None) or 0
        remaining_traffic = total_traffic - used_traffic
        status = (user.status or "").lower() if isinstance(getattr(user, "status", None), str) else ""
        lifetime_used = int(getattr(user, "lifetime_used_traffic", 0) or 0)
        reset_strategy_text, total_possible_traffic = _compute_reset_info(service, user, int(total_traffic))
        config_value = 0
        try:
            single_links = await fetch_service_config_links(service, panel)
        except ValueError:
            single_links = await fetch_user_config_links(panel, getattr(user, "id", None))

        txt = status_messages.get(status, "نامشخص")
        emoji = STATUS_EMOJI.get(status, "")
        status_text = f"{emoji} {txt}".strip() if emoji else txt
        return {
            "code": str(service.code),
            "username": service.username,
            "panel_name": panel.name,
            "status": status or None,
            "status_text": status_text,
            "used_traffic": format_size(used_traffic, decimal_places=2),
            "remaining_traffic": format_size(remaining_traffic, decimal_places=2),
            "total_traffic": format_size(total_traffic, decimal_places=0),
            "used_traffic_bytes": int(used_traffic),
            "remaining_traffic_bytes": int(remaining_traffic),
            "total_traffic_bytes": int(total_traffic),
            "expiration_time": timestamp_to_persian_expiry(user.expire.timestamp())
            if getattr(user, "expire", None)
            else "نامشخص",
            "subscription_url": subscription_url or "نامشخص",
            "ip_limit_text": format_ip_limit(getattr(service, "ip_limit", 0)),
            "helper_subscription_url": helper_url,
            "is_test": bool(getattr(service, "is_test", False)),
            "config_value": f"{config_value:,} تومان",
            "lifetime_used_traffic": format_size(lifetime_used, decimal_places=2),
            "reset_strategy_text": reset_strategy_text,
            "total_possible_traffic": total_possible_traffic,
            "last_connection": relative_time(getattr(user, "online_at", None))
            if getattr(user, "online_at", None)
            else None,
            "last_edit": relative_time(getattr(user, "edit_at", None)) if getattr(user, "edit_at", None) else None,
            "single_config_links": single_links,
        }
    except Exception as e:
        return {
            "code": str(service.code),
            "username": service.username,
            "panel_name": panel.name,
            "status": None,
            "status_text": str(e)[:80],
            **fallback,
        }


async def _get_service_buttons(service: Any, panel: Any, user_id: int) -> dict[str, bool]:
    """Compute button visibility from settings and panel."""

    settings_manager = SettingsManager()
    settings = await settings_manager.get_settings()
    if not settings:
        return {
            "copy_link": False,
            "change_link": False,
            "change_sub": False,
            "tamdid": False,
            "extend_time": False,
            "extra_volume": False,
            "qr": False,
            "other_links": False,
            "transfer_config": False,
            "client_list": False,
            "auto_renew": False,
        }

    is_test = getattr(service, "is_test", False) is True
    is_fair_usage = False
    if service.package_size and panel:
        try:
            from app.db.crud.plans import PlanManager

            plan = await PlanManager().get_plan_by_volume_for_display(
                gb=float(service.package_size) / (1024**3),
                panel_code=int(panel.code),
            )
            if plan and getattr(plan, "plan_type", None) in ("fair_usage", "fair"):
                is_fair_usage = True
        except Exception:
            pass

    btn_zaman = panel_button_enabled(panel, "btn_zaman")
    btn_hajm = panel_button_enabled(panel, "btn_hajm")
    btn_tamdid = panel_button_enabled(panel, "btn_tamdid")
    btn_change_sub = panel_button_enabled(panel, "btn_change_sub")
    btn_other_links = panel_button_enabled(panel, "btn_other_links")
    btn_change_link = panel_button_enabled(panel, "btn_change_link")
    btn_copy_link = panel_button_enabled(panel, "btn_copy_link")
    btn_qr = panel_button_enabled(panel, "btn_qr")
    btn_transfer = panel_button_enabled(panel, "btn_transfer")
    btn_clients = panel_button_enabled(panel, "btn_clients")
    btn_usage_chart = panel_button_enabled(panel, "btn_usage_chart")

    return {
        "copy_link": bool(settings.copy_link_mode) and btn_copy_link,
        "change_link": bool(settings.change_link_mode) and btn_change_link,
        "change_sub": bool(settings.sub_mode) and btn_change_sub,
        "tamdid": bool(settings.tamdid_mode) and btn_tamdid and not is_test,
        "extend_time": bool(settings.extension_mode) and btn_zaman and not is_test,
        "extra_volume": bool(settings.upg_mode) and btn_hajm and not is_fair_usage and not is_test,
        "qr": bool(settings.qr_mode) and btn_qr,
        "other_links": bool(settings.other_links_mode) and btn_other_links,
        "transfer_config": bool(settings.transfer_config_mode) and btn_transfer,
        "client_list": bool(settings.client_list_mode) and btn_clients,
        "usage_chart": bool(getattr(settings, "usage_chart_mode", False)) and btn_usage_chart,
    }


def _parse_client_update(update: Any) -> dict[str, Any]:
    ua = (getattr(update, "user_agent", None) or "").strip() or "نامشخص"
    ip_address = (
        getattr(update, "ip", None)
        or getattr(update, "client_ip", None)
        or getattr(update, "ip_address", None)
        or getattr(update, "request_ip", None)
    )
    hwid = getattr(update, "hwid", None) or getattr(update, "device_id", None) or getattr(update, "device_hwid", None)

    app_name = "نامشخص"
    version = None
    platform = None
    parts = [part.strip() for part in ua.split("/") if part.strip()]
    if parts:
        app_name = parts[0]
    if len(parts) >= 2:
        version = parts[1].split()[0] or None
    if len(parts) >= 3:
        platform = parts[2].split()[0] or None

    created_at = getattr(update, "created_at", None)
    return {
        "created_at": int(created_at.timestamp()) if created_at else 0,
        "created_at_text": Time_Date(created_at)["mf"] if created_at else "نامشخص",
        "time_ago": relative_time(created_at) if created_at else None,
        "user_agent": ua,
        "app_name": app_name,
        "version": version,
        "platform": platform,
        "ip_address": str(ip_address) if ip_address else None,
        "hwid": str(hwid) if hwid else None,
    }


async def _resolve_owned_service(code: int, user_id: int) -> tuple[Any, Any]:
    service_crud = ServiceCRUD()
    found, service = await service_crud.get_service(code)
    if not found or not service or int(service.id) != user_id:
        raise ValueError("سرویس یافت نشد")

    panel = await PanelsManager().get_panel_by_code(service.in_panel)
    if not panel:
        raise ValueError("پنل یافت نشد")
    return service, panel


async def _change_user_link(service_code: int, user_id: int) -> None:
    """Change user's proxy link."""

    service_crud = ServiceCRUD()
    is_found, service = await service_crud.get_service(service_code)

    if not is_found or service.id != user_id:
        raise ValueError("سرویس یافت نشد")
    if getattr(service, "is_test", False) is True:
        raise ValueError("سرویس‌های تست قابل تمدید یا ارتقا نیستند.")

    panels_manager = PanelsManager()
    panel = await panels_manager.get_panel_by_code(service.in_panel)

    if not panel:
        raise ValueError("پنل یافت نشد")

    marzban_api = PasarguardAPI(panel.base_url)
    await marzban_api.modify_user_by_id(
        user_id=require_panel_userid(service),
        user=UserModify(proxy_settings=ProxySettings()),
        token=panel.cookie,
    )


async def _change_user_subscription(service_code: int, user_id: int) -> str:
    """Change user's subscription and return new URL."""

    service_crud = ServiceCRUD()
    is_found, service = await service_crud.get_service(service_code)

    if not is_found or service.id != user_id:
        raise ValueError("سرویس یافت نشد")
    if getattr(service, "is_test", False) is True:
        raise ValueError("سرویس‌های تست قابل تمدید یا ارتقا نیستند.")

    panels_manager = PanelsManager()
    panel = await panels_manager.get_panel_by_code(service.in_panel)

    if not panel:
        raise ValueError("پنل یافت نشد")

    marzban_api = PasarguardAPI(panel.base_url)
    revoked_subscription = await marzban_api.revoke_user_subscription(username=service.username, token=panel.cookie)

    subscription_url = revoked_subscription.subscription_url
    if subscription_url and not subscription_url.startswith("http"):
        subscription_url = f"{panel.base_url}{subscription_url}"

    return subscription_url


@router.post("/webapp/services", response_model=WebAppServicesResponse)
async def get_webapp_services(request: WebAppServicesRequest) -> WebAppServicesResponse:
    """Get user services list with pagination and optional search (requires session_token or init_data)."""

    try:
        user_id = await authenticate_user(
            init_data=request.init_data,
            session_token=request.session_token,
        )
        payload = await build_services_payload(
            user_id, page=request.page, limit=request.limit, search=request.search, panel_code=request.panel_code
        )
        return WebAppServicesResponse(**payload)
    except ValueError as e:
        return WebAppServicesResponse(ok=False, error=str(e))
    except Exception as e:
        return WebAppServicesResponse(ok=False, error=str(e))


@router.post("/webapp/services/detail", response_model=WebAppServiceDetailResponse)
async def get_webapp_service_detail(request: WebAppServiceDetailRequest) -> WebAppServiceDetailResponse:
    """Get single service detail with button visibility flags."""

    try:
        user_id = await authenticate_user(
            init_data=request.init_data,
            session_token=request.session_token,
        )
        service_crud = ServiceCRUD()
        found, service = await service_crud.get_service(request.code)
        if not found or not service or int(service.id) != user_id:
            return WebAppServiceDetailResponse(ok=False, error="سرویس یافت نشد")

        panels_manager = PanelsManager()
        panel = await panels_manager.get_panel_by_code(service.in_panel)
        if not panel:
            return WebAppServiceDetailResponse(ok=False, error="پنل یافت نشد")

        service_data = await _build_service_detail(service, panel)
        buttons_dict = await _get_service_buttons(service, panel, user_id)
        buttons = ServiceButtons(**buttons_dict)

        return WebAppServiceDetailResponse(
            ok=True,
            service=service_data,
            buttons=buttons,
        )
    except ValueError as e:
        return WebAppServiceDetailResponse(ok=False, error=str(e))
    except Exception as e:
        return WebAppServiceDetailResponse(ok=False, error=str(e))


@router.post("/webapp/services/config-links", response_model=WebAppConfigLinksResponse)
async def get_webapp_config_links(request: WebAppConfigLinksRequest) -> WebAppConfigLinksResponse:
    """Single config links with display names (like bot othersSubLinks)."""

    try:
        user_id = await authenticate_user(
            init_data=request.init_data,
            session_token=request.session_token,
        )
        service, panel = await _resolve_owned_service(request.code, user_id)
        links = await fetch_service_config_links(service, panel)
        if not links:
            return WebAppConfigLinksResponse(ok=False, error="هیچ لینکی برای این سرویس پیدا نشد")

        items: list[WebAppConfigLinkItem] = []
        for idx, link in enumerate(links):
            try:
                items.append(
                    WebAppConfigLinkItem(
                        index=idx,
                        name=config_link_display_name(link, idx),
                        url=link,
                    )
                )
            except Exception as item_exc:
                logger.warning("Skipping invalid config link idx=%s service=%s: %s", idx, request.code, item_exc)

        if not items:
            return WebAppConfigLinksResponse(ok=False, error="لینک‌های دریافت‌شده قابل نمایش نیستند")

        return WebAppConfigLinksResponse(
            ok=True,
            links=items,
            total=len(items),
            page=1,
            total_pages=1,
        )
    except ValueError as e:
        return WebAppConfigLinksResponse(ok=False, error=str(e))
    except Exception as e:
        logger.exception("config-links failed for service=%s: %s", request.code, e)
        return WebAppConfigLinksResponse(ok=False, error="خطا در دریافت لینک‌های کانفیگ")


@router.post("/webapp/services/clients", response_model=WebAppClientsResponse)
async def get_webapp_service_clients(request: WebAppClientsRequest) -> WebAppClientsResponse:
    """Active subscription clients for a service."""

    try:
        user_id = await authenticate_user(
            init_data=request.init_data,
            session_token=request.session_token,
        )
        service, panel = await _resolve_owned_service(request.code, user_id)
        updates = await PasarguardAPI(panel.base_url).get_user_sub_update_list_by_username(
            username=service.username,
            token=panel.cookie,
        )
        clients = [WebAppClientItem(**_parse_client_update(update)) for update in (updates.updates or [])]
        return WebAppClientsResponse(ok=True, clients=clients)
    except ValueError as e:
        return WebAppClientsResponse(ok=False, error=str(e))
    except Exception as e:
        return WebAppClientsResponse(ok=False, error=str(e))


@router.post("/webapp/change_link", response_model=WebAppChangeResponse)
async def change_user_link(request: WebAppChangeLinkRequest) -> WebAppChangeResponse:
    """Change user's proxy link."""

    try:
        user_id = await authenticate_user(
            init_data=request.init_data,
            username=request.username,
            password=request.password,
            session_token=request.session_token,
        )

        await _change_user_link(request.code, user_id)
        return WebAppChangeResponse(ok=True)

    except ValueError as e:
        return WebAppChangeResponse(ok=False, error=str(e))
    except Exception as e:
        return WebAppChangeResponse(ok=False, error=str(e))


@router.post("/webapp/change_sub", response_model=WebAppChangeResponse)
async def change_user_subscription(request: WebAppChangeSubscriptionRequest) -> WebAppChangeResponse:
    """Change user's subscription URL."""

    try:
        user_id = await authenticate_user(
            init_data=request.init_data,
            username=request.username,
            password=request.password,
            session_token=request.session_token,
        )

        subscription_url = await _change_user_subscription(request.code, user_id)
        return WebAppChangeResponse(ok=True, subscription_url=subscription_url)

    except ValueError as e:
        return WebAppChangeResponse(ok=False, error=str(e))
    except Exception as e:
        return WebAppChangeResponse(ok=False, error=str(e))
