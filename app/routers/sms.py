"""
SMS router for handling card-to-card payment notifications.
"""

import asyncio
import hmac
import json
import re
import time
from typing import Any
from urllib.parse import parse_qs

from fastapi import APIRouter, HTTPException, Request
from telethon import Button

import config
from app import Kenzo
from app.db.crud.auto_card import CRUDAutoCard
from app.db.crud.settings import SettingsManager
from app.db.crud.transactions import TransactionCRUD
from app.db.crud.user import UserCRUD
from app.logger import LogType, get_logger
from app.services.billing.payment_bonus import calculate_payment_bonus
from app.services.payments.auto_card_sms_parser import build_sms_envelope, extract_deposit_rial
from app.services.send_queue import enqueue
from app.utils.formatting.dates import Time_Date

logger = get_logger(__name__)
sms_router = APIRouter()

_SMS_SECRET_MIN_LENGTH = 16
_FAST_CONFIRM_SECONDS = 30
_SLOW_CONFIRM_SECONDS = 600


def _extract_api_key(request: Request, body_key: str | None) -> str | None:
    """Resolve API key from header first, then body (legacy)."""
    header_key = request.headers.get("x-api-key") or request.headers.get("X-Api-Key")
    if header_key:
        return header_key.strip()
    auth = request.headers.get("authorization") or request.headers.get("Authorization")
    if auth:
        auth = auth.strip()
        if auth.lower().startswith("bearer "):
            return auth[7:].strip()
        return auth
    return body_key.strip() if body_key else None


def _is_valid_api_key(api_key: str | None) -> bool:
    """Check the supplied key against SMS_WEBHOOK_SECRET; fail closed when it is unset or weak."""
    secret = (config.SMS_WEBHOOK_SECRET or "").strip()
    if len(secret) < _SMS_SECRET_MIN_LENGTH:
        logger.warning("SMS webhook rejected: SMS_WEBHOOK_SECRET is not configured or too short")
        return False
    if not api_key:
        return False
    return hmac.compare_digest(api_key.encode("utf-8"), secret.encode("utf-8"))


# SMS Service Functions
async def process_payment_sms(sms_text: str) -> None:
    """Process SMS text for card-to-card payment."""

    parsed = extract_deposit_rial(sms_text)
    if not parsed:
        logger.info("SMS ignored: no deposit amount matched")
        return

    amount = parsed.amount_rial
    logger.info(
        "SMS deposit parsed bank_id=%s amount_rial=%s",
        parsed.bank_id,
        amount,
    )

    auto_card_crud = CRUDAutoCard()
    payment_record = await auto_card_crud.claim_by_amount(amount)

    if not payment_record:
        logger.info("SMS ignored: no pending auto-card invoice for amount_rial=%s", amount)
        return

    await _process_payment(payment_record, amount)


async def _process_payment(payment_record: Any, amount: int) -> None:
    """Process the payment and update user balance."""

    user_crud = UserCRUD()
    transaction_crud = TransactionCRUD()

    settings = await SettingsManager().get_settings()
    bonus = await calculate_payment_bonus(
        amount=payment_record.first_amount,
        bonus_enabled=settings.auto_bonus_enabled,
        bonus_percent=settings.auto_bonus_percent,
    )
    total_amount = payment_record.first_amount + bonus

    # Add money to user account (with bonus)
    new_balance = await user_crud.Add_Money(user_id=payment_record.id, Money=total_amount)

    # Create transaction record (store original amount, not with bonus)
    await transaction_crud.create(
        user_id=payment_record.id, amount=payment_record.first_amount, method="auto", status="approved"
    )

    # Get transaction statistics
    transaction_stats = await _get_user_transaction_stats(payment_record.id)

    # Send notification to user (with bonus info)
    await _notify_user(
        payment_record, new_balance, bonus, settings.auto_bonus_percent if settings.auto_bonus_enabled else 0
    )

    # Send log to channel
    await _log_payment(
        payment_record,
        new_balance,
        transaction_stats,
        bonus,
        settings.auto_bonus_percent if settings.auto_bonus_enabled else 0,
        cart_num=getattr(settings, "cart_num", None),
        cart_name=getattr(settings, "cart_name", None),
    )

    # Clean up payment record
    await CRUDAutoCard().delete_by_amount(amount)


def _format_duration(seconds: int) -> str:
    """Format duration seconds as a Persian human-readable string."""
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    parts: list[str] = []
    if hours:
        parts.append(f"{hours} ساعت")
    if minutes:
        parts.append(f"{minutes} دقیقه")
    if secs or not parts:
        parts.append(f"{secs} ثانیه")
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} و {parts[1]}"
    return f"{parts[0]} و {parts[1]} و {parts[2]}"


def _speed_flag(seconds: int) -> str:
    """Return a speed label for unusually fast/slow confirmations."""
    if seconds < _FAST_CONFIRM_SECONDS:
        return " · ⚡ تایید سریع"
    if seconds > _SLOW_CONFIRM_SECONDS:
        return " · 🐢 تایید دیر"
    return ""


def _mask_card(cart_num: Any) -> str:
    """Mask card number as first4****last4."""
    if cart_num is None:
        return "نامشخص"
    digits = re.sub(r"\D", "", str(cart_num))
    if len(digits) < 8:
        return digits or "نامشخص"
    return f"{digits[:4]}****{digits[-4:]}"


async def _get_user_transaction_stats(user_id: int) -> dict[str, int]:
    """Get user's transaction statistics."""

    transaction_crud = TransactionCRUD()
    manual_approved, manual_rejected, auto_approved, auto_rejected = await asyncio.gather(
        transaction_crud.count_user_transactions(user_id, status="approved", method="manual"),
        transaction_crud.count_user_transactions(user_id, status="rejected", method="manual"),
        transaction_crud.count_user_transactions(user_id, status="approved", method="auto"),
        transaction_crud.count_user_transactions(user_id, status="rejected", method="auto"),
    )

    return {
        "manual_approved": manual_approved,
        "manual_rejected": manual_rejected,
        "auto_approved": auto_approved,
        "auto_rejected": auto_rejected,
    }


async def _notify_user(payment_record: Any, new_balance: int, bonus: int = 0, bonus_percent: int = 0) -> None:
    """Send notification to user about successful payment."""
    message = f"✅ تراکنش کارت به کارت ({payment_record.code}) تایید شد\n---\n💸 مبلغ {payment_record.first_amount:,} تومان به کیف پولتان اضافه شد"
    if bonus > 0:
        message += f"\n🎁 بونوس: +{int(bonus):,} تومان ({bonus_percent}%)"
        message += f"\n💰 مجموع: {int(payment_record.first_amount + bonus):,} تومان"
    await Kenzo.send_message(
        entity=payment_record.id,
        message=message,
        parse_mode="html",
        buttons=[[Button.inline(text=f"موجودی جدید {int(new_balance):,} تومان", data="no_action")]],
    )


async def _log_payment(
    payment_record: Any,
    new_balance: int,
    stats: dict[str, int],
    bonus: int = 0,
    bonus_percent: int = 0,
    cart_num: Any = None,
    cart_name: Any = None,
) -> None:
    """Log payment to channel."""

    username = await _get_telegram_username(payment_record.id)
    credited = int(payment_record.first_amount) + int(bonus)
    prev_balance = int(new_balance) - credited
    confirmed_ts = int(time.time())
    created_ts = int(payment_record.time or confirmed_ts)
    duration_seconds = max(0, confirmed_ts - created_ts)
    duration_label = _format_duration(duration_seconds)
    speed = _speed_flag(duration_seconds)
    created_label = Time_Date(created_ts).get("jf", str(created_ts))
    confirmed_label = Time_Date(confirmed_ts).get("jf", str(confirmed_ts))
    card_label = _mask_card(cart_num)
    card_owner = str(cart_name).strip() if cart_name else "نامشخص"

    lines = [
        "✅ فاکتور کارت‌به‌کارت خودکار پرداخت شد",
        "",
        f"🧾 شماره فاکتور: <code>{payment_record.code}</code>",
        f"💵 مبلغ فاکتور: <code>{payment_record.amount:,}</code> ریال",
        f"💶 مبلغ شارژ: <code>{payment_record.first_amount:,}</code> تومان",
    ]
    if bonus > 0:
        lines.append(f"🎁 بونوس: +<code>{int(bonus):,}</code> تومان ({bonus_percent}%)")
        lines.append(f"💰 مجموع واریز: <code>{credited:,}</code> تومان")
    lines.extend(
        [
            f"🏦 کارت مقصد: <code>{card_label}</code> — {card_owner}",
            "",
            f"👤 نام کاربری: {username}",
            f"🆔 آیدی عددی: <code>{payment_record.id}</code> · "
            f"<a href='tg://user?id={payment_record.id}'>برو به پروفایل کاربر</a>",
            "",
            f"💳 موجودی قبلی: <code>{prev_balance:,}</code> تومان",
            f"💳 موجودی جدید: <code>{int(new_balance):,}</code> تومان",
            "",
            f"⏰ زمان ساخت فاکتور: <code>{created_label}</code>",
            f"✅ زمان تایید: <code>{confirmed_label}</code>",
            f"⌛ مدت تا تایید: <code>{duration_label}</code>{speed}",
            "",
            f"📊 دستی: تایید {stats['manual_approved']:,} | رد {stats['manual_rejected']:,}",
            f"🤖 خودکار: تایید {stats['auto_approved']:,} | رد {stats['auto_rejected']:,}",
            "",
            (
                f"#auto_card #payment_approved #invoice_{payment_record.code} "
                f"#uid_{payment_record.id} #charge_{payment_record.first_amount}" + (" #bonus" if bonus > 0 else "")
            ),
        ]
    )
    log_message = "\n".join(lines)
    await enqueue(
        message=log_message,
        log_type=LogType.AUTO_CARD,
        parse_mode="html",
        buttons=[[Button.inline(text=f"موجودی جدید {int(new_balance):,} تومان", data="no_action")]],
    )


async def _get_telegram_username(user_id: int) -> str:
    """Get Telegram username for user via Telethon entity lookup."""
    try:
        entity = await Kenzo.get_entity(user_id)
        username = getattr(entity, "username", None)
        return f"@{username}" if username else "این کاربر نام کاربری ندارد"
    except Exception:
        return "خطا در دریافت اطلاعات کاربر"


@sms_router.post("/sms")
async def receive_sms_webhook(request: Request) -> dict:
    """Handle SMS webhook for card-to-card payments (JSON or form-urlencoded)."""

    raw = await request.body()
    content_type = (request.headers.get("content-type") or "").lower()
    json_body: dict[str, Any] | None = None
    form_body: dict[str, Any] | None = None

    if "application/x-www-form-urlencoded" in content_type:
        parsed = parse_qs(raw.decode("utf-8", errors="replace"), keep_blank_values=True)
        form_body = {k: (v[0] if len(v) == 1 else v) for k, v in parsed.items()}
    else:
        try:
            payload = json.loads(raw.decode("utf-8"))
            if isinstance(payload, dict):
                json_body = payload
        except Exception:
            text = raw.decode("utf-8", errors="replace")
            if "=" in text:
                parsed = parse_qs(text, keep_blank_values=True)
                form_body = {k: (v[0] if len(v) == 1 else v) for k, v in parsed.items()}

    envelope = build_sms_envelope(json_body=json_body, form_body=form_body)
    if envelope is None:
        logger.warning("SMS webhook ignored: empty or invalid body")
        return {"status": "ignored", "reason": "invalid_body"}

    api_key = _extract_api_key(request, envelope.key)
    if not _is_valid_api_key(api_key):
        logger.warning("Invalid SMS webhook key")
        return {"Telegram": "@AmirKenzoo"}

    try:
        await process_payment_sms(envelope.text)
        logger.info("SMS payment processed successfully")
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Failed to process SMS payment: {e}")
        raise HTTPException(status_code=500, detail="Failed to process SMS payment") from None


logger.debug("SMS router loaded successfully")
