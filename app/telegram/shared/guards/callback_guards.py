"""Shared callback permission guards for service flows."""

from __future__ import annotations

import contextlib
import re

from httpx import HTTPStatusError

from app.db.crud.panels import PanelsManager
from app.db.crud.plans import PlanManager
from app.db.crud.services import ServiceCRUD
from app.db.crud.settings import SettingsManager
from app.services.billing.renewal import require_panel_userid
from app.services.panels.api_client import PasarguardAPI
from app.services.panels.settings import (
    panel_button_enabled,
    panel_has_time_plans,
    panel_has_volume_plans,
)
from app.telegram.keyboards.common import glass_inline_button
from app.telegram.state import get_data
from config import ADMIN_ID

SESSION_RESTART_CALLBACK = "SessionRestart"

SESSION_EXPIRED_TEXT = (
    "⏰ **این دکمه منقضی شده است**\n\n"
    "به‌دلیل گذشت زمان، وضعیت قبلی شما ذخیره نشده است.\n"
    "برای ادامه از دکمه زیر استفاده کنید:"
)

_ACCESS_DENIED_DISABLED = "این گزینه در حال حاضر غیرفعال است."
_ACCESS_DENIED_ADMIN = "این بخش فقط برای ادمین در دسترس است."

_ADMIN_ONLY_PREFIXES = (
    "AdminConfigToggle:",
    "AdminConfigVolume:",
    "AdminConfigVolumeCustom:",
    "AdminConfigTime:",
    "DeleteServiceAdmin:",
    "DeleteServiceAdmin_confirm:",
    "BackToServiceListAdmin:",
)

_TAMDID_FLOW_PREFIXES = (
    "TamdidVPN_",
    "SelectDurationGroupForTamdid:",
    "SelectPlanTamdid_",
    "confirm_purchase_tamdid_",
    "ApplyCodeTakhfifTamdid",
    "Confirm_buy_tamdid",
)
_SERVICE_GUARD_PREFIXES = (
    "ChangeLink:",
    "ChangeSub:",
    "KharidSize:",
    "upgSize@",
    "KharidZaman:",
    "upgTime@",
    "getQrcode:",
    "TransferConfig:",
    "othersSubLinks:",
    "NextSubLinks:",
    "PrevSubLinks:",
    "showSubLink:",
    "get_single_links:",
    "get_xhttp_links:",
    "showClients:",
    "UsageChart:",
    "UsageChartDay:",
    "DeleteService:",
    "ConfirmDelete:",
    *_TAMDID_FLOW_PREFIXES,
)


def _is_service_user_action_callback(data: str) -> bool:
    return any(data.startswith(prefix) for prefix in _SERVICE_GUARD_PREFIXES)


def _extract_service_code_from_callback(data: str) -> str | None:
    for prefix in (
        "othersSubLinks:",
        "showClients:",
        "get_single_links:",
        "get_xhttp_links:",
        "showSubLink:",
        "NextSubLinks:",
        "PrevSubLinks:",
        "UsageChart:",
        "UsageChartDay:",
        "TransferConfig:",
        "DeleteService:",
        "ConfirmDelete:",
        "getQrcode:",
        "KharidSize:",
        "KharidZaman:",
    ):
        if data.startswith(prefix):
            parts = data.split(":")
            if len(parts) >= 2 and str(parts[1]).isdigit():
                return parts[1]
    for pattern in (
        r"^TamdidVPN_(.+)$",
        r"^ChangeLink:[^:]+:(.+)$",
        r"^ChangeSub:[^:]+:(.+)$",
    ):
        match = re.match(pattern, data)
        if match:
            return match.group(1)
    if data.startswith("upgSize@") or data.startswith("upgTime@"):
        parts = data.split("@")
        if len(parts) >= 2:
            return parts[1]
    return None


async def _resolve_service_for_callback(user_id: int, data: str):
    service_code = _extract_service_code_from_callback(data)
    if service_code:
        return await ServiceCRUD().get_service(code=service_code)

    if any(data.startswith(prefix) for prefix in _TAMDID_FLOW_PREFIXES[1:]) or data.startswith(
        ("upgSize@", "upgTime@")
    ):
        config_id = await get_data(user_id, "ConfigID")
        if config_id:
            return await ServiceCRUD().get_service(code=config_id)
    if data.startswith("ConfirmDelete:"):
        return await ServiceCRUD().get_service(code=data.split(":")[1])
    return False, None


async def _get_panel_user_status(serv_msg, panel) -> str | None:
    try:
        user = await PasarguardAPI(panel.base_url).get_user_by_id(
            user_id=require_panel_userid(serv_msg), token=panel.cookie
        )
        return (user.status or "").lower()
    except HTTPStatusError:
        return None
    except Exception:
        return None


def _user_service_button_allowed(
    data: str,
    serv_msg,
    panel,
    settings,
    *,
    panel_status: str | None = None,
) -> bool:
    is_test = getattr(serv_msg, "is_test", False) is True
    status = (panel_status or "").lower()

    if data.startswith("ChangeLink:"):
        return bool(settings.change_link_mode and panel_button_enabled(panel, "btn_change_link"))
    if data.startswith("ChangeSub:"):
        return bool(settings.sub_mode and panel_button_enabled(panel, "btn_change_sub"))
    if data.startswith("KharidSize:") or data.startswith("upgSize@"):
        return bool(
            not is_test
            and settings.upg_mode
            and panel_button_enabled(panel, "btn_hajm")
            and panel_has_volume_plans(panel)
        )
    if data.startswith("KharidZaman:") or data.startswith("upgTime@"):
        return bool(
            not is_test
            and settings.extension_mode
            and panel_button_enabled(panel, "btn_zaman")
            and panel_has_time_plans(panel)
        )
    if any(
        data.startswith(prefix)
        for prefix in (
            "showSubLink:",
            "NextSubLinks:",
            "PrevSubLinks:",
            "get_single_links:",
            "get_xhttp_links:",
        )
    ):
        return bool(settings.other_links_mode and panel_button_enabled(panel, "btn_other_links"))
    if data.startswith("UsageChartDay:"):
        return bool(settings.usage_chart_mode and panel_button_enabled(panel, "btn_usage_chart"))
    if data.startswith("TamdidVPN_") or any(data.startswith(prefix) for prefix in _TAMDID_FLOW_PREFIXES[1:]):
        return bool(not is_test and settings.tamdid_mode and panel_button_enabled(panel, "btn_tamdid"))
    if data.startswith("getQrcode:"):
        return bool(settings.qr_mode and panel_button_enabled(panel, "btn_qr"))
    if data.startswith("ConfirmDelete:"):
        return bool(
            settings.del_service_mode
            and panel_button_enabled(panel, "btn_del_service")
            and status in ("disabled", "expired", "limited")
        )

    if data.startswith("TransferConfig:"):
        return bool(settings.transfer_config_mode and panel_button_enabled(panel, "btn_transfer"))
    if data.startswith("othersSubLinks:"):
        return bool(settings.other_links_mode and panel_button_enabled(panel, "btn_other_links"))
    if data.startswith("showClients:"):
        return bool(settings.client_list_mode and panel_button_enabled(panel, "btn_clients"))
    if data.startswith("UsageChart:"):
        return bool(settings.usage_chart_mode and panel_button_enabled(panel, "btn_usage_chart"))

    if data.startswith("DeleteService:"):
        return bool(
            settings.del_service_mode
            and panel_button_enabled(panel, "btn_del_service")
            and status in ("disabled", "expired", "limited")
        )
    return False


async def _is_fair_usage_volume_blocked(serv_msg) -> bool:
    if not serv_msg.package_size:
        return False
    panel = await PanelsManager().get_panel_by_code(code=serv_msg.in_panel)
    if not panel:
        return False
    plan = await PlanManager().get_plan_by_volume_for_display(
        gb=serv_msg.package_size / (1024**3),
        panel_code=panel.code,
    )
    return bool(plan and hasattr(plan, "plan_type") and plan.plan_type in ("fair_usage", "fair"))


async def guard_admin_only_service_callback(event, data: str) -> bool:
    """Block admin-only callbacks for regular users (shared messages)."""
    if (
        data.startswith("service_info_admin:") or any(data.startswith(p) for p in _ADMIN_ONLY_PREFIXES)
    ) and event.sender_id not in ADMIN_ID:
        await event.answer(_ACCESS_DENIED_ADMIN, alert=True)
        return False
    return True


async def guard_user_service_callback(event, data: str) -> bool:
    """Return False when the callback must be blocked (alert already sent)."""
    if event.sender_id in ADMIN_ID:
        return True
    if not _is_service_user_action_callback(data):
        return True

    _, serv_msg = await _resolve_service_for_callback(event.sender_id, data)
    if not serv_msg:
        await event.answer("❌ این کانفیگ برای شما نیست!", alert=True)
        return False
    if int(serv_msg.id or 0) != int(event.sender_id):
        await event.answer("❌ این کانفیگ برای شما نیست!", alert=True)
        return False

    panel = await PanelsManager().get_panel_by_code(code=serv_msg.in_panel)
    if not panel:
        await event.answer("پنل یافت نشد!", alert=True)
        return False

    settings = await SettingsManager().get_settings()
    panel_status = None
    if data.startswith(("DeleteService:", "ConfirmDelete:")):
        panel_status = await _get_panel_user_status(serv_msg, panel)

    if not _user_service_button_allowed(data, serv_msg, panel, settings, panel_status=panel_status):
        await event.answer(_ACCESS_DENIED_DISABLED, alert=True)
        return False

    if data.startswith(("KharidSize:", "upgSize@")) and await _is_fair_usage_volume_blocked(serv_msg):
        await event.answer("امکان خرید حجم اضافی برای این پلن وجود ندارد.", alert=True)
        return False

    return True


async def run_service_callback_guards(event, data: str) -> bool:
    """Return True when the callback may proceed; False when blocked (alert sent)."""
    if not await guard_admin_only_service_callback(event, data):
        return False
    return await guard_user_service_callback(event, data)


async def notify_session_expired(event) -> None:
    """Replace the stale message with expiry text and a glass restart button."""
    with contextlib.suppress(Exception):
        await event.answer()
    buttons = [[glass_inline_button("شروع مجدد", data=SESSION_RESTART_CALLBACK)]]
    with contextlib.suppress(Exception):
        await event.edit(SESSION_EXPIRED_TEXT, buttons=buttons)
        return
    await event.respond(SESSION_EXPIRED_TEXT, buttons=buttons)
