"""Fulfill VPN config renew after direct-pay wallet credit."""

from __future__ import annotations

from typing import Any

from pasarguard import PasarguardAPI

from app import Kenzo
from app.db.crud.discount_codes import DiscountCodeManager
from app.db.crud.panels import PanelsManager
from app.db.crud.plans import PlanManager
from app.db.crud.services import ServiceCRUD
from app.logger import LogType, get_logger
from app.services.billing.renewal import (
    PaidRenewalError,
    execute_paid_service_renewal,
    require_panel_userid,
)
from app.telegram.shared.utils.logging import send_log_message
from app.telegram.state import clear_user
from app.utils.formatting.conversions import convert_storage
from app.utils.formatting.dates import Time_Date
from app.utils.formatting.traffic import format_size
from app.utils.text.bot_texts import get_bot_text

logger = get_logger(__name__)

RENEWAL_SUCCESS_DEFAULT = (
    "✅ از اعتماد شما ممنونیم !\n\n"
    "🎉 اکانت شما با مشخصات زیر تمدید شد :\n\n"
    "🎫 کد سرویس: {service_code}\n"
    "📝 نام کانفیگ: {config_name}\n"
    "📥 پلن انتخابی: {plan_name}\n"
    "📥 حجم جدید شما: {new_volume}\n"
    "⏳ تاریخ انقضا اکانت: {expiration_date}\n\n"
    "💰 مبلغ {price} هزارتومان از موجودی شما کسر شد.\n\n"
    "💵 موجودی جدید کیف‌پول شما:\n"
    "{new_balance} هزارتومان\n\n"
    "🌐 جهت مدیریت اکانت ها روی /myaccount کلیک کنید."
)


async def create_vpn_renew_for_user(
    user_id: int,
    *,
    amount: int,
    payload: dict[str, Any] | None = None,
    discount_code: str | None = None,
) -> tuple[bool, str]:
    """Renew an existing VPN config after direct-pay credit. Idempotent caller claims first."""
    payload = payload if isinstance(payload, dict) else {}
    service_code = payload.get("service_code")
    panel_code = payload.get("panel")
    plan_id = payload.get("selected_plan_id")
    discount_code = discount_code or payload.get("discount_code")

    if service_code is None or panel_code is None or plan_id is None:
        return False, "missing_context"

    try:
        plan_id_int = int(plan_id)
        service_code_int = int(service_code)
    except TypeError, ValueError:
        return False, "invalid_ids"

    plan = await PlanManager().get_plan(plan_id_int)
    if not plan:
        return False, "plan_not_found"

    ok, service = await ServiceCRUD().get_service(code=service_code_int)
    if not ok or not service:
        return False, "service_not_found"
    if int(service.id) != int(user_id):
        return False, "not_owner"
    if getattr(service, "is_test", False) is True:
        return False, "test_service"

    panel = await PanelsManager().get_panel_by_code(code=panel_code)
    if not panel:
        return False, "panel_not_found"

    price = int(amount)
    if discount_code:
        status, _res = await DiscountCodeManager().validate_discount_code(code=discount_code, user_id=user_id)
        if not status:
            discount_code = None

    try:
        panel_user = await PasarguardAPI(panel.base_url).get_user_by_id(
            user_id=require_panel_userid(service),
            token=panel.cookie,
        )
        new_hajm, new_balance = await execute_paid_service_renewal(
            service,
            panel,
            plan,
            price=price,
            panel_user=panel_user,
        )
    except PaidRenewalError as exc:
        logger.warning("direct_pay renew paid error user=%s: %s", user_id, exc)
        return False, str(exc)
    except Exception as exc:
        logger.exception("direct_pay renew error user=%s: %s", user_id, exc)
        return False, str(exc)

    if discount_code:
        await DiscountCodeManager().update_discount_usage(code=discount_code)

    gig = float(plan.storage)
    plan_name = convert_storage(
        gig,
        getattr(plan, "plan_type", None),
        getattr(plan, "data_limit_reset_strategy", None),
    )
    ip_limit = getattr(plan, "ip_limit", 0)
    plan_name_with_limit = f"{plan_name} [{ip_limit}] کاربره" if ip_limit and ip_limit > 0 else plan_name
    config_name = str(payload.get("config_name") or service.username or "")

    success_text_template = await get_bot_text(
        key="renewal_success_text",
        default=RENEWAL_SUCCESS_DEFAULT,
        lang="fa",
    )
    expiration_date_text = f"{plan.duration} روز دیگر"
    txt = (
        success_text_template.replace("{service_code}", str(service_code_int))
        .replace("{config_name}", config_name)
        .replace("{plan_name}", plan_name_with_limit)
        .replace("{new_volume}", format_size(new_hajm, decimal_places=0))
        .replace("{expiration_date}", expiration_date_text)
        .replace("{price}", f"{price:,}")
        .replace("{new_balance}", f"{new_balance:,}")
    )

    if discount_code:
        log_text = (
            f"📢 ** تمدید جدید با کدتخفیف (پرداخت مستقیم)**\n\n"
            f"👤 شناسه کاربر: `{user_id}`\n"
            f"📅 تاریخ خرید (میلادی): `{Time_Date()['mf']}`\n"
            f"📅 تاریخ خرید (شمسی): `{Time_Date()['jf']}`\n"
            f"🎫 کد سرویس: `{service_code_int}`\n"
            f"🎟 **کدتخفیف استفاده شده:** `{discount_code}`\n"
            f"**🔷 اسم کانفیگ:** `{config_name}`\n"
            f"**📥 حجم انتخابی کاربر:** {plan_name}\n"
            f"**📥 حجم جدید کاربر :** `{format_size(new_hajm, decimal_places=2)}`\n"
            f"**⏳ زمان جدید کانفیگ: {plan.duration} روز**\n"
            f"💸 مبلغ بدون تخفیف: `{int(plan.price):,}` تومان\n"
            f"💸 مبلغ پرداخت شده: `{price:,}` تومان\n"
            f"💵 موجودی جدید کاربر: `{new_balance:,}` تومان\n."
        )
    else:
        log_text = (
            f"📢 ** تمدید جدید بدون کدتخفیف (پرداخت مستقیم)**\n\n"
            f"👤 شناسه کاربر: `{user_id}`\n"
            f"📅 تاریخ خرید (میلادی): `{Time_Date()['mf']}`\n"
            f"📅 تاریخ خرید (شمسی): `{Time_Date()['jf']}`\n"
            f"🎫 کد سرویس: `{service_code_int}`\n"
            f"**🔷 اسم کانفیگ:** `{config_name}`\n"
            f"**📥 حجم انتخابی کاربر:** {plan_name}\n"
            f"**📥 حجم جدید کاربر :** `{format_size(new_hajm, decimal_places=2)}`\n"
            f"**⏳ زمان جدید کانفیگ: {plan.duration} روز**\n"
            f"💸 مبلغ پرداخت شده: `{price:,}` تومان\n"
            f"💵 موجودی جدید کاربر: `{new_balance:,}` تومان\n."
        )

    try:
        await Kenzo.send_message(int(user_id), txt)
    except Exception as exc:
        logger.warning("direct_pay renew notify user=%s: %s", user_id, exc)

    await send_log_message(LogType.OTHER, message=log_text)
    await clear_user(user_id)
    return True, ""
