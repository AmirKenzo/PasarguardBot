"""Service upgrades: extend expiry time, add extra data volume, transfer config ownership.

Webapp equivalents of the Telegram bot's KharidZaman/KharidSize/TransferConfig
callbacks (app/telegram/user/services/callbacks.py and messages.py).
"""

from datetime import timedelta

from fastapi import APIRouter
from pasarguard import PasarguardAPI, UserModify

from app import Kenzo
from app.db.crud.plans import PlanManager
from app.db.crud.services import ServiceCRUD
from app.db.crud.user import UserCRUD, update_Money
from app.logger import LogType, get_logger
from app.models.webapp import (
    TimePlanItem,
    VolumePlanItem,
    WebAppExtendTimeConfirmRequest,
    WebAppExtendTimeConfirmResponse,
    WebAppExtendTimeOptionsRequest,
    WebAppExtendTimeOptionsResponse,
    WebAppExtraVolumeConfirmRequest,
    WebAppExtraVolumeConfirmResponse,
    WebAppExtraVolumeOptionsRequest,
    WebAppExtraVolumeOptionsResponse,
    WebAppTransferConfigRequest,
    WebAppTransferConfigResponse,
)
from app.routers.webapp.auth import authenticate_user
from app.routers.webapp.services import _resolve_owned_service
from app.services.billing.renewal import require_panel_userid
from app.services.panels.settings import (
    get_panel_time_plan,
    get_panel_volume_plan,
    panel_time_plans,
    panel_volume_plans,
)
from app.services.send_queue import enqueue
from app.utils.formatting.conversions import gigabytes_to_bytes, to_unix_timestamp

logger = get_logger(__name__)
router = APIRouter()


@router.post("/webapp/services/extend-time/options", response_model=WebAppExtendTimeOptionsResponse)
async def get_extend_time_options(request: WebAppExtendTimeOptionsRequest) -> WebAppExtendTimeOptionsResponse:
    """Time plans available to extend a service's expiry."""

    try:
        user_id = await authenticate_user(init_data=request.init_data, session_token=request.session_token)
        service, panel = await _resolve_owned_service(request.code, user_id)
        if getattr(service, "is_test", False) is True:
            return WebAppExtendTimeOptionsResponse(ok=False, error="سرویس‌های تست قابل تمدید نیستند")

        plans = panel_time_plans(panel)
        if not plans:
            return WebAppExtendTimeOptionsResponse(ok=False, error="پلن زمان اضافه‌ای برای این پنل تعریف نشده است")

        return WebAppExtendTimeOptionsResponse(
            ok=True,
            service_code=str(request.code),
            panel_name=panel.name,
            plans=[TimePlanItem(id=p["id"], duration_days=p["duration_days"], price=p["price"]) for p in plans],
        )
    except ValueError as e:
        return WebAppExtendTimeOptionsResponse(ok=False, error=str(e))
    except Exception as e:
        return WebAppExtendTimeOptionsResponse(ok=False, error=str(e))


@router.post("/webapp/services/extend-time/confirm", response_model=WebAppExtendTimeConfirmResponse)
async def confirm_extend_time(request: WebAppExtendTimeConfirmRequest) -> WebAppExtendTimeConfirmResponse:
    """Confirm a time-extension purchase: deduct balance, push panel expiry forward."""

    try:
        user_id = await authenticate_user(init_data=request.init_data, session_token=request.session_token)
        service, panel = await _resolve_owned_service(request.code, user_id)
        if getattr(service, "is_test", False) is True:
            return WebAppExtendTimeConfirmResponse(ok=False, error="سرویس‌های تست قابل تمدید نیستند")

        plan = get_panel_time_plan(panel, request.plan_id)
        if not plan:
            return WebAppExtendTimeConfirmResponse(ok=False, error="پلن زمان انتخاب‌شده معتبر نیست")

        price = int(plan["price"])
        added_days = int(plan["duration_days"])

        user = await UserCRUD().read_user(user_id)
        balance = int(getattr(user, "amount", 0) or 0) if user else 0
        if balance < price:
            return WebAppExtendTimeConfirmResponse(
                ok=False, error="موجودی کیف پول کافی نیست. ابتدا موجودی خود را افزایش دهید."
            )

        api = PasarguardAPI(panel.base_url)
        panel_user = await api.get_user_by_id(user_id=require_panel_userid(service), token=panel.cookie)
        new_time = panel_user.expire + timedelta(days=added_days)

        await api.modify_user_by_id(
            user_id=require_panel_userid(service), user=UserModify(expire=new_time), token=panel.cookie
        )

        new_balance = await update_Money(user_id=user_id, Money=-price)
        await ServiceCRUD().update_service(
            code=request.code,
            expiration_time=new_time.timestamp(),
            warning=0,
            warning_time=0,
            expire_notified=False,
        )

        await enqueue(
            message=(
                f"⏳ **افزایش مدت زمان اعتبار (وب‌اپ)**\n\n"
                f"👻 شناسه کاربر: `{user_id}`\n"
                f"🎫 کد سرویس: `{request.code}`\n"
                f"**🔷 اسم کانفیگ:** `{service.username}`\n"
                f"📅 مدت زمان خریداری شده: `{added_days}` روز\n"
                f"💵 مبلغ کسر شده: `{price:,}` **تومان**\n"
                f"💰 موجودی جدید: `{new_balance:,}` **تومان**"
            ),
            log_type=LogType.OTHER,
        )

        return WebAppExtendTimeConfirmResponse(
            ok=True,
            new_balance=new_balance,
            new_expiration_timestamp=to_unix_timestamp(new_time),
            added_days=added_days,
            amount_paid=price,
            config_name=service.username,
        )
    except ValueError as e:
        return WebAppExtendTimeConfirmResponse(ok=False, error=str(e))
    except Exception as e:
        logger.exception("extend-time confirm failed for service=%s: %s", request.code, e)
        return WebAppExtendTimeConfirmResponse(ok=False, error="خطا در افزایش زمان سرویس")


@router.post("/webapp/services/extra-volume/options", response_model=WebAppExtraVolumeOptionsResponse)
async def get_extra_volume_options(request: WebAppExtraVolumeOptionsRequest) -> WebAppExtraVolumeOptionsResponse:
    """Volume plans available to add extra data to a service."""

    try:
        user_id = await authenticate_user(init_data=request.init_data, session_token=request.session_token)
        service, panel = await _resolve_owned_service(request.code, user_id)
        if getattr(service, "is_test", False) is True:
            return WebAppExtraVolumeOptionsResponse(ok=False, error="سرویس‌های تست قابل ارتقا نیستند")

        if service.package_size:
            current_plan = await PlanManager().get_plan_by_volume_for_display(
                gb=float(service.package_size) / (1024**3), panel_code=panel.code
            )
            if current_plan and getattr(current_plan, "plan_type", None) in ("fair_usage", "fair"):
                return WebAppExtraVolumeOptionsResponse(
                    ok=False, error="امکان خرید حجم اضافی برای پلن‌های مصرف منصفانه وجود ندارد"
                )

        plans = panel_volume_plans(panel)
        if not plans:
            return WebAppExtraVolumeOptionsResponse(ok=False, error="پلن حجم اضافه‌ای برای این پنل تعریف نشده است")

        return WebAppExtraVolumeOptionsResponse(
            ok=True,
            service_code=str(request.code),
            panel_name=panel.name,
            plans=[VolumePlanItem(id=p["id"], storage_gb=p["storage_gb"], price=p["price"]) for p in plans],
        )
    except ValueError as e:
        return WebAppExtraVolumeOptionsResponse(ok=False, error=str(e))
    except Exception as e:
        return WebAppExtraVolumeOptionsResponse(ok=False, error=str(e))


@router.post("/webapp/services/extra-volume/confirm", response_model=WebAppExtraVolumeConfirmResponse)
async def confirm_extra_volume(request: WebAppExtraVolumeConfirmRequest) -> WebAppExtraVolumeConfirmResponse:
    """Confirm a volume-top-up purchase: deduct balance, raise panel data limit."""

    try:
        user_id = await authenticate_user(init_data=request.init_data, session_token=request.session_token)
        service, panel = await _resolve_owned_service(request.code, user_id)
        if getattr(service, "is_test", False) is True:
            return WebAppExtraVolumeConfirmResponse(ok=False, error="سرویس‌های تست قابل ارتقا نیستند")

        plan = get_panel_volume_plan(panel, request.plan_id)
        if not plan:
            return WebAppExtraVolumeConfirmResponse(ok=False, error="پلن حجم انتخاب‌شده معتبر نیست")

        price = int(plan["price"])
        added_bytes = gigabytes_to_bytes(float(plan["storage_gb"]))

        user = await UserCRUD().read_user(user_id)
        balance = int(getattr(user, "amount", 0) or 0) if user else 0
        if balance < price:
            return WebAppExtraVolumeConfirmResponse(
                ok=False, error="موجودی کیف پول کافی نیست. ابتدا موجودی خود را افزایش دهید."
            )

        api = PasarguardAPI(panel.base_url)
        panel_user = await api.get_user_by_id(user_id=require_panel_userid(service), token=panel.cookie)
        new_limit = int(panel_user.data_limit or 0) + added_bytes

        await api.modify_user_by_id(
            user_id=require_panel_userid(service), user=UserModify(data_limit=new_limit), token=panel.cookie
        )

        new_balance = await update_Money(user_id=user_id, Money=-price)
        await ServiceCRUD().update_service(code=request.code, package_size=new_limit, low_volume_notified=False)

        await enqueue(
            message=(
                f"🔼 **خرید حجم (وب‌اپ)**\n\n"
                f"👻 شناسه کاربر: `{user_id}`\n"
                f"🎫 کد سرویس: `{request.code}`\n"
                f"**🔷 اسم کانفیگ:** `{service.username}`\n"
                f"📦 حجم اضافه‌شده: `{plan['storage_gb']}` گیگ\n"
                f"💵 مبلغ کسر شده: `{price:,}` **تومان**\n"
                f"💰 موجودی جدید: `{new_balance:,}` **تومان**"
            ),
            log_type=LogType.OTHER,
        )

        return WebAppExtraVolumeConfirmResponse(
            ok=True,
            new_balance=new_balance,
            new_total_traffic_bytes=new_limit,
            added_bytes=added_bytes,
            amount_paid=price,
            config_name=service.username,
        )
    except ValueError as e:
        return WebAppExtraVolumeConfirmResponse(ok=False, error=str(e))
    except Exception as e:
        logger.exception("extra-volume confirm failed for service=%s: %s", request.code, e)
        return WebAppExtraVolumeConfirmResponse(ok=False, error="خطا در افزایش حجم سرویس")


@router.post("/webapp/services/transfer", response_model=WebAppTransferConfigResponse)
async def transfer_config(request: WebAppTransferConfigRequest) -> WebAppTransferConfigResponse:
    """Transfer a service's ownership to another Telegram user (must have started the bot)."""

    try:
        user_id = await authenticate_user(init_data=request.init_data, session_token=request.session_token)
        service, panel = await _resolve_owned_service(request.code, user_id)

        target_id = int(request.target_user_id)
        if target_id == user_id:
            return WebAppTransferConfigResponse(ok=False, error="نمی‌توانید کانفیگ را به خودتان انتقال دهید")

        target_user = await UserCRUD().read_user(user_id=target_id)
        if not target_user:
            return WebAppTransferConfigResponse(ok=False, error="کاربر مقصد ربات را استارت نکرده است")

        await ServiceCRUD().update_service(code=request.code, id=target_user.id)

        try:
            await PasarguardAPI(panel.base_url).modify_user_by_id(
                user_id=require_panel_userid(service),
                user=UserModify(note=str(target_user.id)),
                token=panel.cookie,
            )
        except Exception as e:
            logger.warning("Failed to update panel note on transfer: %s", e)

        await Kenzo.send_message(
            entity=target_user.id,
            message=(
                f"✅ کاربر عزیز یک کانفیگ با کد ( {request.code} ) از کاربر ( {user_id} ) برای شما واگذار شد. "
                "برای مشاهده کانفیگ به بخش سرویس‌های من مراجعه کنید. "
                "برای امنیت بیشتر یک‌بار کانفیگ را تغییر لینک بدهید."
            ),
        )
        await enqueue(
            message=(
                f"#واگذاری_کانفیگ (وب‌اپ)\nکدکانفیگ: {request.code}\nتوسط: {user_id} به کاربر {target_user.id} واگذار شد"
            ),
            log_type=LogType.OTHER,
        )

        return WebAppTransferConfigResponse(ok=True, target_user_id=int(target_user.id))
    except ValueError as e:
        return WebAppTransferConfigResponse(ok=False, error=str(e))
    except Exception as e:
        logger.exception("transfer config failed for service=%s: %s", request.code, e)
        return WebAppTransferConfigResponse(ok=False, error="خطا در انتقال کانفیگ")
