"""Zibal gateway (API v1): client plus the shared deposit flow used by the bot, web app, callback and job.

Flow: request -> buyer pays on Zibal's start page -> Zibal redirects the buyer to our callback -> we call
verify. Zibal's verify does not take the amount, so the paid amount and order id it reports are checked
against the local row before crediting. Crediting is one atomic DB transaction, so the callback, the bot
"check" button and the poller can all race safely.

Test mode uses Zibal's public test merchant ("zibal"), which needs no account; it is only offered to admins.
"""

from __future__ import annotations

import time
from typing import Any

import httpx
from telethon import Button

from app import Kenzo
from app.db.crud.settings import SettingsManager
from app.db.crud.zibal_payments import OPEN_STATUSES, ZibalPaymentCRUD
from app.db.models.zibal_payment import ZibalPayment
from app.logger import LogType, get_logger
from app.services.billing.direct_pay_fulfillment import (
    cancel_after_crypto_expire,
    try_fulfill_after_crypto_credit,
)
from app.services.billing.payment_bonus import calculate_payment_bonus
from app.services.payments.zibal_config import (
    BASE_URL,
    bonus_percent,
    callback_url,
    deposit_limits,
    is_available_for,
    is_ready,
    is_sandbox,
    merchant_for,
    start_pay_url,
)
from app.telegram.shared.utils.logging import send_log_message

logger = get_logger(__name__)

MAX_OPEN_PAYMENTS = 3
# A Zibal payment that is still unpaid after this long is closed locally.
LOCAL_EXPIRY_SECONDS = 30 * 60
CODE_OK = 100
CODE_ALREADY_VERIFIED = 201
CODE_NOT_PAID = 202
CODE_INVALID_TRACK = 203

STATUS_LABELS = {
    "pending": "در انتظار پرداخت",
    "completed": "پرداخت شده",
    "failed": "ناموفق",
    "canceled": "لغو شده",
    "expired": "منقضی شده",
}

ERROR_MESSAGES = {
    102: "مرچنت زیبال پیدا نشد.",
    103: "مرچنت زیبال غیرفعال است.",
    104: "مرچنت زیبال نامعتبر است.",
    105: "مبلغ باید بیشتر از ۱۰۰ تومان باشد.",
    106: "آدرس بازگشت (callbackUrl) نامعتبر است.",
    113: "مبلغ بیشتر از سقف مجاز تراکنش در زیبال است.",
    202: "پرداخت انجام نشده یا ناموفق بوده است.",
    203: "شناسه پرداخت (trackId) نامعتبر است.",
}


class ZibalError(Exception):
    """A Zibal API or flow error with a user-facing Persian message."""

    def __init__(self, message: str, code: int | None = None):
        super().__init__(message)
        self.message = message
        self.code = code


def status_label(status: str | None) -> str:
    return STATUS_LABELS.get(status or "", status or "نامشخص")


def payment_url(payment: ZibalPayment) -> str | None:
    return start_pay_url(payment.track_id) if payment.track_id else None


# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except TypeError, ValueError:
        return None


class ZibalClient:
    def __init__(self, merchant: str, *, transport: httpx.AsyncBaseTransport | None = None):
        self.merchant = merchant
        self._transport = transport

    async def _post(self, path: str, body: dict[str, Any]) -> tuple[int | None, dict[str, Any]]:
        if not self.merchant:
            raise ZibalError("مرچنت زیبال تنظیم نشده است.")
        try:
            async with httpx.AsyncClient(base_url=BASE_URL, timeout=20.0, transport=self._transport) as client:
                response = await client.post(path, json={"merchant": self.merchant, **body})
        except httpx.HTTPError as e:
            logger.error("Zibal request %s failed: %s", path, e)
            raise ZibalError("ارتباط با زیبال برقرار نشد. کمی بعد دوباره تلاش کنید.") from e
        try:
            data = response.json()
        except ValueError:
            data = None
        code = _as_int(data.get("result")) if isinstance(data, dict) else None
        if code is None:
            logger.warning("Zibal %s -> HTTP %s | body=%s", path, response.status_code, response.text[:500])
            raise ZibalError(f"پاسخ نامعتبر از زیبال (HTTP {response.status_code}).")
        if code not in (CODE_OK, CODE_ALREADY_VERIFIED):
            logger.warning("Zibal %s -> result %s: %s", path, code, data.get("message"))
        return code, data

    async def request_payment(self, *, amount_rial: int, description: str, callback: str, order_id: str) -> str:
        """Open a payment and return its trackId."""
        code, data = await self._post(
            "/v1/request",
            {"amount": int(amount_rial), "callbackUrl": callback, "description": description, "orderId": order_id},
        )
        track_id = str(data.get("trackId") or "")
        if code != CODE_OK or not track_id:
            raise ZibalError(ERROR_MESSAGES.get(code or 0, f"خطای زیبال (کد {code})."), code)
        return track_id

    async def verify(self, track_id: str) -> tuple[int | None, dict[str, Any]]:
        return await self._post("/v1/verify", {"trackId": _as_int(track_id) or track_id})

    async def inquiry(self, track_id: str) -> tuple[int | None, dict[str, Any]]:
        return await self._post("/v1/inquiry", {"trackId": _as_int(track_id) or track_id})


def _client_for(payment: ZibalPayment, settings) -> ZibalClient:
    return ZibalClient(merchant_for(settings, payment.sandbox))


async def test_connection(merchant: str) -> tuple[bool, str]:
    """Open a throwaway 1,000-toman payment; success proves the merchant and server IP are accepted."""
    url = callback_url() or "https://example.com/zibal/callback"
    try:
        track_id = await ZibalClient(merchant.strip()).request_payment(
            amount_rial=10_000, description="Connection test", callback=url, order_id="ZB-TEST"
        )
    except ZibalError as e:
        return False, e.message
    return True, f"اتصال برقرار است. trackId: {track_id}"


# ---------------------------------------------------------------------------
# Deposit flow
# ---------------------------------------------------------------------------


async def create_deposit(user_id: int, amount: int, *, source: str) -> ZibalPayment:
    settings = await SettingsManager().get_settings()
    if not is_available_for(settings, user_id):
        raise ZibalError("درگاه زیبال در حال حاضر فعال نیست.")
    min_amount, max_amount = deposit_limits(settings)
    if amount < min_amount or amount > max_amount:
        raise ZibalError(f"مبلغ باید بین {min_amount:,} تا {max_amount:,} تومان باشد.")
    crud = ZibalPaymentCRUD()
    if await crud.count_open_for_user(user_id) >= MAX_OPEN_PAYMENTS:
        raise ZibalError("بیش از سه پرداخت باز دارید. ابتدا آن‌ها را پرداخت کنید یا چند دقیقه صبر کنید.")
    callback = callback_url()
    if not callback:
        raise ZibalError("آدرس بازگشت (WEBAPP_URL با https) تنظیم نشده است.")

    sandbox = is_sandbox(settings)
    payment = await crud.create(user_id=user_id, amount=amount, sandbox=sandbox, source=source)
    try:
        track_id = await ZibalClient(merchant_for(settings, sandbox)).request_payment(
            amount_rial=amount * 10,
            description=f"شارژ کیف پول کاربر {user_id}",
            callback=callback,
            order_id=payment.order_id,
        )
    except ZibalError:
        await crud.delete(payment.id)
        raise
    payment = await crud.update(payment.id, track_id=track_id) or payment
    await send_log_message(
        LogType.CRYPTO,
        message=(
            f"#پرداخت_جدید_زیبال{' 🧪 (تستی)' if sandbox else ''} ({'وب‌اپ' if source == 'webapp' else 'ربات'})\n"
            f"👤 شناسه کاربر: <code>{user_id}</code> | <a href='tg://user?id={user_id}'>پروفایل کاربر</a>\n"
            f"🧾 شناسه سفارش: <code>{payment.order_id}</code>\n"
            f"💵 مبلغ: <code>{amount:,}</code> تومان"
        ),
        parse_mode="html",
    )
    return payment


def _mismatch(payment: ZibalPayment, data: dict[str, Any]) -> str | None:
    """Why a successful verify answer must not be credited, or None when it matches the local row."""
    paid_amount = _as_int(data.get("amount"))
    if paid_amount is not None and paid_amount != int(payment.amount) * 10:
        return f"amount {paid_amount} != {int(payment.amount) * 10}"
    order_id = data.get("orderId")
    if order_id and str(order_id) != payment.order_id:
        return f"orderId {order_id} != {payment.order_id}"
    return None


async def verify_payment(payment: ZibalPayment, *, buyer_canceled: bool = False) -> ZibalPayment:
    """Ask Zibal whether the payment went through and apply the answer (credit, close or keep waiting)."""
    if payment.status not in OPEN_STATUSES or not payment.track_id:
        return payment
    crud = ZibalPaymentCRUD()
    settings = await SettingsManager().get_settings()
    client = _client_for(payment, settings)
    expired = time.time() - int(payment.created_at or 0) > LOCAL_EXPIRY_SECONDS
    try:
        code, data = await client.verify(payment.track_id)
        if code == CODE_ALREADY_VERIFIED and data.get("amount") is None:
            # A repeated verify may omit the details; inquiry returns them for the same trackId.
            inquiry_code, inquiry = await client.inquiry(payment.track_id)
            if inquiry_code == CODE_OK:
                data = {**inquiry, **{k: v for k, v in data.items() if v is not None}}
    except ZibalError as e:
        logger.warning("Zibal verify failed for %s: %s", payment.order_id, e.message)
        if expired:
            return await _close_payment(payment, "expired")
        await crud.update(payment.id)  # bump updated_at so the poller rotates to other payments
        return payment

    if code in (CODE_OK, CODE_ALREADY_VERIFIED):
        problem = _mismatch(payment, data)
        if problem:
            logger.error(
                "Zibal verify for %s does not match the local payment (%s); not crediting", payment.order_id, problem
            )
            return await _close_payment(payment, "failed")
        return await _credit_payment(payment, ref_id=data.get("refNumber"), card_pan=data.get("cardNumber"))
    if code == CODE_NOT_PAID and buyer_canceled:
        return await _close_payment(payment, "canceled")
    if code == CODE_INVALID_TRACK:
        logger.error("Zibal verify for %s says the trackId is invalid; closing as failed", payment.order_id)
        return await _close_payment(payment, "failed")
    if expired:
        return await _close_payment(payment, "expired")
    await crud.update(payment.id)
    return payment


async def handle_callback(track_id: str, success: str) -> ZibalPayment | None:
    """Buyer returned from Zibal. The query string is untrusted: the result always comes from verify."""
    payment = await ZibalPaymentCRUD().get_by_track_id(track_id)
    if not payment:
        return None
    return await verify_payment(payment, buyer_canceled=(success or "").strip() != "1")


# ---------------------------------------------------------------------------
# Crediting and notifications
# ---------------------------------------------------------------------------


async def _notify_user(payment: ZibalPayment, text: str, buttons=None) -> None:
    try:
        await Kenzo.send_message(payment.user_id, text, parse_mode="html", buttons=buttons)
    except Exception as e:
        logger.warning("Zibal user notify failed for %s: %s", payment.user_id, e)


async def _credit_payment(payment: ZibalPayment, *, ref_id: Any, card_pan: Any) -> ZibalPayment:
    settings = await SettingsManager().get_settings()
    percent = bonus_percent(settings)
    bonus = await calculate_payment_bonus(amount=int(payment.amount), bonus_enabled=percent > 0, bonus_percent=percent)
    total_amount = int(payment.amount) + bonus
    crud = ZibalPaymentCRUD()
    approved = await crud.approve_and_credit(
        payment.id,
        total_amount,
        ref_id=str(ref_id)[:32] if ref_id not in (None, "") else None,
        card_pan=str(card_pan)[:32] if card_pan and card_pan != "-" else None,
    )
    if not approved:
        return await crud.get(payment.id) or payment
    payment, new_balance = approved

    test_tag = " 🧪 (تستی)" if payment.sandbox else ""
    balance_btn = [[Button.inline(text=f"💳 موجودی: {new_balance:,} تومان", data="no_action")]]
    bonus_line = f"🎁 <b>بونوس:</b> +<code>{bonus:,}</code> تومان ({percent}%)\n" if bonus > 0 else ""
    try:
        if not await try_fulfill_after_crypto_credit(int(payment.id)):
            await _notify_user(
                payment,
                f"🎉 <b>پرداخت زیبال با موفقیت انجام شد!</b>{test_tag}\n\n"
                f"🧾 <b>کد پیگیری:</b> <code>{payment.ref_id or '—'}</code>\n"
                f"💵 <b>مبلغ شارژ:</b> <code>{int(payment.amount):,}</code> تومان\n"
                f"{bonus_line}"
                f"💳 <b>موجودی جدید:</b> <code>{new_balance:,}</code> تومان\n\n"
                f"<code>#Zibal_{payment.order_id}</code>",
                buttons=balance_btn,
            )
        await send_log_message(
            LogType.CRYPTO,
            message=(
                f"#پرداخت_زیبال{test_tag}\n<b>✅ پرداخت زیبال کاربر تأیید شد</b>\n\n"
                f"<b>👤 شناسه کاربری:</b> <code>{payment.user_id}</code> | "
                f"<a href='tg://user?id={payment.user_id}'>پروفایل کاربر</a>\n"
                f"<b>🧾 شناسه سفارش:</b> <code>{payment.order_id}</code>\n"
                f"<b>🔖 کد پیگیری:</b> <code>{payment.ref_id or '—'}</code>\n"
                f"<b>💳 کارت پرداخت‌کننده:</b> <code>{payment.card_pan or '—'}</code>\n"
                f"<b>💵 مبلغ شارژ:</b> <code>{int(payment.amount):,}</code> تومان\n"
                f"{bonus_line}"
                f"<b>💳 موجودی جدید کاربر:</b> <code>{new_balance:,}</code> تومان"
            ),
            parse_mode="html",
            buttons=balance_btn,
        )
    except Exception as e:
        logger.error("Zibal post-credit notification failed for %s: %s", payment.order_id, e)
    return payment


async def _close_payment(payment: ZibalPayment, status: str) -> ZibalPayment:
    closed = await ZibalPaymentCRUD().close_if_open(payment.id, status)
    if not closed:
        return await ZibalPaymentCRUD().get(payment.id) or payment
    payment = closed
    await cancel_after_crypto_expire(int(payment.id))
    await _notify_user(
        payment,
        "<b>#اطلاع_رسانی</b>\n\n"
        f"<b>📅 پرداخت زیبال</b> <code>{payment.order_id}</code> <b>{status_label(status)}.</b>\n"
        f"<b>💵 مبلغ:</b> <code>{int(payment.amount):,}</code> <b>تومان</b>\n"
        "اگر مبلغی از حساب شما کسر شده، طبق قوانین بانکی حداکثر تا ۷۲ ساعت به حساب‌تان برمی‌گردد.",
        buttons=[[Button.inline(text=f"🚫 {status_label(status)}", data="no_action")]],
    )
    await send_log_message(
        LogType.CRYPTO,
        message=(
            f"#پرداخت_زیبال_بسته_شد{' 🧪' if payment.sandbox else ''}\n"
            f"👤 شناسه کاربر: <code>{payment.user_id}</code>\n"
            f"🧾 شناسه سفارش: <code>{payment.order_id}</code>\n"
            f"💵 مبلغ: <code>{int(payment.amount):,}</code> تومان\n"
            f"📌 وضعیت: {status_label(status)}"
        ),
        parse_mode="html",
    )
    return payment


__all__ = [
    "MAX_OPEN_PAYMENTS",
    "ZibalClient",
    "ZibalError",
    "create_deposit",
    "handle_callback",
    "is_ready",
    "payment_url",
    "status_label",
    "test_connection",
    "verify_payment",
]
