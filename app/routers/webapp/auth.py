"""Auth: Telegram init-data login, phone OTP login, session, and logout."""

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
from app.db.crud.transactions import TransactionCRUD
from app.db.crud.user import UserCRUD, add_user
from app.logger import LogType, get_logger
from app.models.webapp import (
    LogoutRequest,
    PhoneLoginStartRequest,
    PhoneLoginVerifyRequest,
    WebAppChangeResponse,
    WebAppInfoResponse,
    WebAppUserData,
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
from app.utils.formatting.conversions import to_unix_timestamp
from app.utils.formatting.dates import Time_Date
from app.utils.security.webapp_auth import (
    create_session_token,
    parse_session_token_async,
    validate_webapp_data,
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

        phone = user_record.number or "نامشخص"

        notification_text = (
            f"🔐 **ورود به وب‌سایت**\n\n"
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

    expiration_ts = to_unix_timestamp(discount_code.expiration_date) if discount_code.expiration_date else None

    return {
        "code": discount_code.code,
        "percent": int(discount_code.discount_percentage) if discount_code.discount_percentage else 0,
        "times_used": int(discount_code.times_used) if discount_code.times_used else 0,
        "usage_limit": int(discount_code.usage_limit) if discount_code.usage_limit else 0,
        "is_public": bool(discount_code.is_public),
        "expiration_timestamp": expiration_ts,
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
    is_safe_mode = bool(user_record.safe_mode) if user_record else False
    phone_number = user_record.number if user_record else None

    join_date = to_unix_timestamp(user_record.time_s) if user_record and user_record.time_s else None

    discount_info = await _get_discount_info(user_id)
    transaction_stats = await _get_transaction_stats(user_id)

    return {
        "id": user_id,
        "username": telegram_user.username if telegram_user else None,
        "first_name": telegram_user.first_name if telegram_user else None,
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
    """Build user payload without services (fast login/info).

    Opening the WebApp is a valid first contact with the bot, same as /start,
    so a user with no DB row yet (never messaged the bot) gets registered here.
    """

    if user_record is None:
        user_record = await UserCRUD().read_user(user_id)
        if user_record is None:
            await add_user(user_id=user_id, step="start", time_s=Time_Date()["stamp"])
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
        return int(payload["uid"])

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
        token = create_session_token(int(sess["user_id"]))
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
        revoke_session_token(token)
        return WebAppChangeResponse(ok=True)
    except Exception as e:
        return WebAppChangeResponse(ok=False, error=str(e))
