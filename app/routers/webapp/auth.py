"""Auth, session, OTP login, logout, and web-account endpoints."""

import asyncio
import contextlib
import json
import random
import time as time_module
from typing import Any
from urllib.parse import parse_qsl

from fastapi import APIRouter, Request

from app import Kenzo
from app.db.crud.cryptopayments import get_user_crypto_stats
from app.db.crud.discount_codes import DiscountCodeManager
from app.db.crud.services import get_user_services
from app.db.crud.settings import SettingsManager
from app.db.crud.transactions import TransactionCRUD
from app.db.crud.user import UserCRUD
from app.logger import LogType, get_logger
from app.models.webapp import (
    LogoutRequest,
    PhoneLoginStartRequest,
    PhoneLoginVerifyRequest,
    WebAccountChangePasswordRequest,
    WebAccountChangePasswordResponse,
    WebAccountCreateRequest,
    WebAccountCreateResponse,
    WebAppChangeResponse,
    WebAppInfoResponse,
    WebAppLoginRequest,
    WebAppUserData,
    WebRegistrationModeResponse,
)
from app.routers.webapp.state import (
    get_header_auth,
    otp_key,
    otp_sessions,
    prune_auth_state,
    revoke_session_token,
    revoked_tokens,
)
from app.services.send_queue import enqueue
from app.utils.formatting.dates import Time_Date
from app.utils.security.webapp_auth import (
    create_session_token,
    hash_password_async,
    parse_session_token_async,
    validate_webapp_data,
    verify_password_async,
)

logger = get_logger(__name__)
router = APIRouter()


async def _send_telegram_code(user_id: int, code: str) -> None:
    """Send the OTP code to user's Telegram via Bot API."""
    text = (
        f"**کد ورود شما:** `{code}`\n"
        f"این کد به مدت ۵ دقیقه معتبر است.\n"
        f"اگر شما درخواست ورود نداده‌اید، این پیام را نادیده بگیرید."
    )
    with contextlib.suppress(Exception):
        await Kenzo.send_message(user_id, text)


async def _send_login_notification(
    user_id: int, login_method: str, user_info: str | None = None, user_record: Any | None = None
) -> None:
    """Send login notification to log channel."""
    try:
        if user_record is None:
            user_record = await UserCRUD().read_user(user_id)
        if not user_record:
            return

        username = user_record.web_username or "نامشخص"
        phone = user_record.number or "نامشخص"

        notification_text = (
            f"🔐 **ورود به وب‌سایت**\n\n"
            f"👤 **کاربر:** {username}\n"
            f"📱 **شماره:** {phone}\n"
            f"🆔 **آیدی:** `{user_id}`\n"
            f"🌐 **روش ورود:** {login_method}\n"
            f"⏰ **زمان:** {Time_Date()['jf']}"
        )

        await enqueue(message=notification_text, log_type=LogType.USER_REGISTRATION)

    except Exception as e:
        # Don't fail login if notification fails
        logger.warning("Failed to send login notification: %s", e)


async def _get_discount_info(user_id: int) -> dict[str, Any] | None:
    """Get user's discount code information."""

    discount_manager = DiscountCodeManager()
    discount_code = await discount_manager.get_code_whith_user_id(user_id)

    if not discount_code:
        return None

    expiration_text = (
        f"{Time_Date(discount_code.expiration_date)['jf']} ({Time_Date(discount_code.expiration_date)['remaining_days']})"
        if discount_code.expiration_date
        else "نامشخص"
    )

    return {
        "code": discount_code.code,
        "percent": int(discount_code.discount_percentage) if discount_code.discount_percentage else 0,
        "usage": f"{int(discount_code.times_used) if discount_code.times_used else 0}/{int(discount_code.usage_limit) if discount_code.usage_limit else 0}",
        "type": "عمومی" if discount_code.is_public else "💎 پرایوت 💎",
        "expiration": expiration_text,
    }


def _convert_decimals(obj: Any) -> Any:
    """Convert Decimal objects to int for JSON serialization."""

    if isinstance(obj, dict):
        return {key: _convert_decimals(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [_convert_decimals(item) for item in obj]
    if hasattr(obj, "__class__") and "Decimal" in str(obj.__class__):
        return int(obj)
    return obj


async def _get_transaction_stats(user_id: int) -> dict[str, Any]:
    """Get user's transaction statistics."""

    default_stats = {
        "manual": {"count": 0, "total_amount": 0},
        "crypto": {"count": 0, "total_amount": 0},
    }

    try:
        transaction_crud = TransactionCRUD()

        manual_stats, crypto_stats = await asyncio.gather(
            transaction_crud.get_user_transaction_stats(user_id, "manual"),
            get_user_crypto_stats(user_id),
        )

        return {
            "manual": _convert_decimals(manual_stats),
            "crypto": _convert_decimals(crypto_stats),
        }
    except Exception as e:
        logger.error("Error getting transaction stats: %s", e)
        return default_stats


async def _build_user_profile(
    user_id: int, user_record: Any | None, telegram_user: WebAppUserData | None
) -> dict[str, Any]:
    """Build user profile data."""

    invite_count = int(user_record.invite) if user_record and user_record.invite else 0
    balance_amount = int(user_record.amount) if user_record and user_record.amount else 0
    is_safe_mode = bool(user_record.safe) if user_record else False
    phone_number = user_record.number if user_record else None

    join_date = None
    if user_record and user_record.time_s:
        join_date = Time_Date(user_record.time_s).get("jf")

    discount_info = await _get_discount_info(user_id)
    transaction_stats = await _get_transaction_stats(user_id)

    return {
        "id": user_id,
        "username": (telegram_user.username if telegram_user else None)
        or (user_record.web_username if user_record else None),
        "first_name": (telegram_user.first_name if telegram_user else None)
        or (user_record.web_username if user_record else None),
        "photo_url": telegram_user.photo_url if telegram_user else None,
        "invite": invite_count,
        "amount": balance_amount,
        "safe": is_safe_mode,
        "number": phone_number,
        "join_date": join_date,
        "discount": discount_info,
        "transactions": transaction_stats,
    }


async def build_user_payload_no_services(
    user_id: int, telegram_user: WebAppUserData | None = None, user_record: Any | None = None
) -> dict[str, Any]:
    """Build user payload without services (fast login/info)."""

    if user_record is None:
        user_record = await UserCRUD().read_user(user_id)

    user_profile = await _build_user_profile(user_id, user_record, telegram_user)
    return {"ok": True, "user": user_profile}


def _merge_request_auth(
    *,
    init_data: str | None = None,
    session_token: str | None = None,
) -> tuple[str | None, str | None]:
    """Prefer secure auth headers; fall back to body/query values for compatibility."""
    header_session, header_init = get_header_auth()
    return header_session or session_token, header_init or init_data


async def authenticate_user(
    init_data: str | None = None,
    username: str | None = None,
    password: str | None = None,
    session_token: str | None = None,
) -> int | None:
    """Authenticate user and return user ID."""
    session_token, init_data = _merge_request_auth(init_data=init_data, session_token=session_token)

    if init_data:
        params = dict(parse_qsl(init_data))
        is_valid, error = validate_webapp_data(params)
        if not is_valid:
            raise ValueError(error)

        user_data = json.loads(params.get("user"))
        return user_data.get("id")

    if session_token:
        prune_auth_state()
        if session_token in revoked_tokens:
            raise ValueError("نشست منقضی شده است")
        ok, err, payload = await parse_session_token_async(session_token)
        if not ok or not payload:
            raise ValueError(err or "توکن نامعتبر است")
        uid = int(payload["uid"])
        # Check session version in DB
        user = await UserCRUD().read_user(uid)
        db_ver = int(getattr(user, "session_version", 0) or 0) if user else 0
        if int(payload.get("ver", 0)) != db_ver:
            raise ValueError("نشست منقضی شده است")
        return uid

    if username and password:
        user_record = await UserCRUD().get_user_by_web_username(username)
        if not user_record or not await verify_password_async(password, user_record.web_password):
            raise ValueError("احراز هویت ناموفق")
        return user_record.id

    raise ValueError("اطلاعات ناقص است")


@router.get("/webapp/info", response_model=WebAppInfoResponse)
async def get_webapp_info(request: Request) -> WebAppInfoResponse:
    """Get user information for web app."""
    _, header_init = get_header_auth()
    # Prefer header; legacy fallback keeps raw Telegram init-data in the query string.
    query_params = dict(parse_qsl(header_init)) if header_init else dict(request.query_params)

    is_valid, error_message = validate_webapp_data(query_params)
    if not is_valid:
        return WebAppInfoResponse(ok=False, error=error_message)

    try:
        user_json = query_params.get("user")
        if not user_json:
            return WebAppInfoResponse(ok=False, error="اطلاعات کاربر یافت نشد")

        user_data = json.loads(user_json)
        user_id = int(user_data.get("id"))

        telegram_user = WebAppUserData(**user_data)

        payload = await build_user_payload_no_services(user_id, telegram_user=telegram_user)
        return WebAppInfoResponse(**payload)

    except Exception as e:
        return WebAppInfoResponse(ok=False, error=str(e))


@router.post("/webapp/login", response_model=WebAppInfoResponse)
async def webapp_login(login_request: WebAppLoginRequest) -> WebAppInfoResponse:
    """Authenticate user and return user information."""

    try:
        user_record = await UserCRUD().get_user_by_web_username(login_request.username)

        if not user_record or not await verify_password_async(login_request.password, user_record.web_password):
            return WebAppInfoResponse(ok=False, error="نام کاربری یا رمز عبور اشتباه است")

        user_ver = await UserCRUD().get_session_version(int(user_record.id))
        token = create_session_token(int(user_record.id), version=user_ver)
        payload = await build_user_payload_no_services(user_record.id, user_record=user_record)
        payload["session_token"] = token

        await _send_login_notification(int(user_record.id), "نام کاربری و رمز عبور", user_record=user_record)

        return WebAppInfoResponse(**payload)

    except Exception as e:
        return WebAppInfoResponse(ok=False, error=str(e))


@router.post("/webapp/otp/start", response_model=WebAppChangeResponse)
async def start_phone_login(req: PhoneLoginStartRequest) -> WebAppChangeResponse:
    """Start phone login: generate OTP and send via Telegram bot."""
    try:
        prune_auth_state()
        user = await UserCRUD().get_user_by_phone(req.phone)
        if not user:
            return WebAppChangeResponse(ok=False, error="شماره پیدا نشد یا کاربر ربات را شروع نکرده است")

        code = f"{random.randint(0, 999999):06d}"
        key = otp_key(str(user.number or req.phone))
        otp_sessions[key] = {
            "code": code,
            "user_id": int(user.id),
            "exp": int(time_module.time()) + 300,
            "attempts": 0,
        }

        await _send_telegram_code(int(user.id), code)
        return WebAppChangeResponse(ok=True)
    except Exception as e:
        return WebAppChangeResponse(ok=False, error=str(e))


@router.post("/webapp/otp/verify", response_model=WebAppInfoResponse)
async def verify_phone_login(req: PhoneLoginVerifyRequest) -> WebAppInfoResponse:
    """Verify OTP and return user payload + session token."""
    try:
        user = await UserCRUD().get_user_by_phone(req.phone)
        if not user:
            return WebAppInfoResponse(ok=False, error="شماره یافت نشد")

        key = otp_key(str(user.number or req.phone))
        sess = otp_sessions.get(key)
        now = int(time_module.time())
        if not sess or sess.get("exp", 0) < now:
            otp_sessions.pop(key, None)
            return WebAppInfoResponse(ok=False, error="کد منقضی شده است. دوباره تلاش کنید")

        if sess.get("attempts", 0) >= 5:
            otp_sessions.pop(key, None)
            return WebAppInfoResponse(ok=False, error="تعداد تلاش‌ها زیاد است. دوباره تلاش کنید")

        if str(sess.get("code")) != str(req.code).strip():
            sess["attempts"] = int(sess.get("attempts", 0)) + 1
            return WebAppInfoResponse(ok=False, error="کد وارد شده نادرست است")

        otp_sessions.pop(key, None)
        user_ver = await UserCRUD().get_session_version(int(sess["user_id"]))
        token = create_session_token(int(sess["user_id"]), version=user_ver)
        payload = await build_user_payload_no_services(int(user.id), user_record=user)
        payload["session_token"] = token

        await _send_login_notification(int(user.id), "شماره تلفن و کد تایید", user_record=user)

        return WebAppInfoResponse(**payload)
    except Exception as e:
        return WebAppInfoResponse(ok=False, error=str(e))


@router.get("/webapp/info/session", response_model=WebAppInfoResponse)
async def get_webapp_info_session(
    request: Request,
    session_token: str | None = None,
) -> WebAppInfoResponse:
    """Get user information for web app using a persisted session token.

    Prefer `Authorization: Bearer` / `X-Session-Token` headers. Query param is
    accepted only as a deprecated fallback.
    """
    token, _ = _merge_request_auth(session_token=session_token)
    if not token:
        return WebAppInfoResponse(ok=False, error="توکن احراز هویت ارسال نشده است")
    prune_auth_state()
    if token in revoked_tokens:
        return WebAppInfoResponse(ok=False, error="نشست منقضی شده است")
    ok, err, payload = await parse_session_token_async(token)
    if not ok or not payload:
        return WebAppInfoResponse(ok=False, error=err or "توکن نامعتبر است")
    uid = int(payload["uid"])  # type: ignore
    user = await UserCRUD().read_user(uid)
    db_ver = int(getattr(user, "session_version", 0) or 0) if user else 0
    if int(payload.get("ver", 0)) != db_ver:
        return WebAppInfoResponse(ok=False, error="نشست منقضی شده است")
    try:
        payload = await build_user_payload_no_services(int(uid))
        payload["session_token"] = token
        return WebAppInfoResponse(**payload)
    except Exception as e:
        return WebAppInfoResponse(ok=False, error=str(e))


@router.post("/webapp/logout", response_model=WebAppChangeResponse)
async def logout(req: LogoutRequest) -> WebAppChangeResponse:
    """Revoke a session token so it can no longer be used."""
    try:
        token, _ = _merge_request_auth(session_token=req.session_token)
        if not token:
            return WebAppChangeResponse(ok=False, error="توکن احراز هویت ارسال نشده است")
        ok, err, payload = await parse_session_token_async(token)
        if not ok or not payload:
            return WebAppChangeResponse(ok=False, error=err or "توکن نامعتبر است")
        await UserCRUD().bump_session_version(int(payload["uid"]))
        revoke_session_token(token)
        return WebAppChangeResponse(ok=True)
    except Exception as e:
        return WebAppChangeResponse(ok=False, error=str(e))


@router.post("/webapp/account/create", response_model=WebAccountCreateResponse)
async def create_web_account(request: WebAccountCreateRequest) -> WebAccountCreateResponse:
    """Create web account for user."""

    try:
        settings_manager = SettingsManager()
        settings = await settings_manager.get_settings()

        if not settings or not settings.web_account_creation_enabled:
            return WebAccountCreateResponse(
                ok=False, message="ساخت اکانت وب غیرفعال است", error="ساخت اکانت وب موقتاً غیرفعال می‌باشد"
            )

        if settings.web_registration_mode == "none":
            return WebAccountCreateResponse(
                ok=False, message="ساخت اکانت وب غیرفعال است", error="ساخت اکانت وب موقتاً غیرفعال می‌باشد"
            )

        if len(request.username) < 3:
            return WebAccountCreateResponse(
                ok=False, message="نام کاربری باید حداقل ۳ کاراکتر باشد", error="نام کاربری کوتاه است"
            )

        if len(request.password) < 6:
            return WebAccountCreateResponse(
                ok=False, message="رمز عبور باید حداقل ۶ کاراکتر باشد", error="رمز عبور کوتاه است"
            )

        user_crud = UserCRUD()
        existing_user = await user_crud.get_user_by_web_username(request.username)
        if existing_user:
            return WebAccountCreateResponse(
                ok=False, message="این نام کاربری قبلاً استفاده شده است", error="نام کاربری تکراری است"
            )

        # Authenticate via header (preferred) or body session_token.
        user_id = None
        token, init_data = _merge_request_auth(session_token=request.session_token)
        if token or init_data:
            try:
                user_id = await authenticate_user(session_token=token, init_data=init_data)
            except ValueError:
                return WebAccountCreateResponse(ok=False, message="احراز هویت ناموفق", error="توکن نامعتبر است")

        if settings.web_registration_mode == "customers" and user_id:
            user_services = await get_user_services(user_id)
            if isinstance(user_services, str) or not user_services:
                return WebAccountCreateResponse(
                    ok=False, message="فقط مشتریان می‌توانند اکانت بسازند", error="شما سرویس فعالی ندارید"
                )

        if user_id:
            success = await user_crud.update_user(
                user_id,
                web_username=request.username,
                web_password=await hash_password_async(request.password),
            )
            if success:
                return WebAccountCreateResponse(ok=True, message="اکانت وب با موفقیت ایجاد شد")
            return WebAccountCreateResponse(
                ok=False, message="خطا در ایجاد اکانت", error="خطا در به‌روزرسانی اطلاعات کاربر"
            )
        return WebAccountCreateResponse(
            ok=False, message="این endpoint نیاز به احراز هویت دارد", error="کاربر احراز هویت نشده است"
        )

    except Exception as e:
        return WebAccountCreateResponse(ok=False, message="خطا در ایجاد اکانت", error=str(e))


@router.post("/webapp/account/change-password", response_model=WebAccountChangePasswordResponse)
async def change_web_account_password(request: WebAccountChangePasswordRequest) -> WebAccountChangePasswordResponse:
    """Change web account password."""

    try:
        token, init_data = _merge_request_auth(session_token=request.session_token)
        if not token and not init_data:
            return WebAccountChangePasswordResponse(
                ok=False, message="این endpoint نیاز به احراز هویت دارد", error="توکن احراز هویت ارسال نشده است"
            )

        try:
            user_id = await authenticate_user(session_token=token, init_data=init_data)
        except ValueError as e:
            return WebAccountChangePasswordResponse(ok=False, message="احراز هویت ناموفق", error=str(e))

        if len(request.new_password) < 6:
            return WebAccountChangePasswordResponse(
                ok=False, message="رمز عبور جدید باید حداقل ۶ کاراکتر باشد", error="رمز عبور کوتاه است"
            )

        user_crud = UserCRUD()
        user_record = await user_crud.read_user(user_id)

        if not user_record or not user_record.web_username:
            return WebAccountChangePasswordResponse(ok=False, message="اکانت وب یافت نشد", error="کاربر اکانت وب ندارد")

        # No need to verify current password - direct password change
        success = await user_crud.update_user(user_id, web_password=await hash_password_async(request.new_password))

        if success:
            return WebAccountChangePasswordResponse(ok=True, message="رمز عبور با موفقیت تغییر کرد")
        return WebAccountChangePasswordResponse(
            ok=False, message="خطا در تغییر رمز عبور", error="خطا در به‌روزرسانی رمز عبور"
        )

    except Exception as e:
        return WebAccountChangePasswordResponse(ok=False, message="خطا در تغییر رمز عبور", error=str(e))


@router.get("/webapp/registration/status", response_model=WebRegistrationModeResponse)
async def get_registration_status() -> WebRegistrationModeResponse:
    """Get current registration mode status."""

    try:
        settings_manager = SettingsManager()
        settings = await settings_manager.get_settings()

        if not settings:
            return WebRegistrationModeResponse(ok=False, message="تنظیمات یافت نشد", error="تنظیمات سیستم یافت نشد")

        mode_text = {
            "all": "همه کاربران می‌توانند اکانت بسازند",
            "customers": "فقط مشتریان می‌توانند اکانت بسازند",
            "none": "ساخت اکانت غیرفعال است",
        }

        return WebRegistrationModeResponse(
            ok=True, message=f"وضعیت ثبت‌نام: {mode_text.get(settings.web_registration_mode, 'نامشخص')}"
        )

    except Exception as e:
        return WebRegistrationModeResponse(ok=False, message="خطا در دریافت وضعیت ثبت‌نام", error=str(e))
