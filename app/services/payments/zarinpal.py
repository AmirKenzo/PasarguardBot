"""Zarinpal gateway (API v4): client plus the shared deposit flow used by the bot, web app, callback and job.

Flow: request -> buyer pays on Zarinpal's StartPay page -> Zarinpal redirects the buyer to our callback
-> we call verify. Only a verify answer of 100/101 credits the user, and crediting is one atomic DB
transaction, so the callback, the bot "check" button and the poller can all race safely.

Test mode talks to sandbox.zarinpal.com, which needs no account; it is only offered to admins.
"""

from __future__ import annotations

import time
from typing import Any

import httpx
from telethon import Button

from app import Kenzo
from app.db.crud.settings import SettingsManager
from app.db.crud.zarinpal_payments import OPEN_STATUSES, ZarinpalPaymentCRUD
from app.db.models.zarinpal_payment import ZarinpalPayment
from app.logger import LogType, get_logger
from app.services.billing.direct_pay_fulfillment import (
    cancel_after_crypto_expire,
    try_fulfill_after_crypto_credit,
)
from app.services.billing.payment_bonus import calculate_payment_bonus
from app.services.payments.zarinpal_config import (
    base_url,
    bonus_percent,
    callback_url,
    deposit_limits,
    is_available_for,
    is_ready,
    is_sandbox,
    merchant_id_for,
    start_pay_url,
)
from app.telegram.shared.utils.logging import send_log_message

logger = get_logger(__name__)

MAX_OPEN_PAYMENTS = 3
# A Zarinpal session that is still unpaid after this long is closed locally.
LOCAL_EXPIRY_SECONDS = 30 * 60
SUCCESS_CODES = (100, 101)
CODE_NOT_PAID = -51

STATUS_LABELS = {
    "pending": "در انتظار پرداخت",
    "completed": "پرداخت شده",
    "failed": "ناموفق",
    "canceled": "لغو شده",
    "expired": "منقضی شده",
}

ERROR_MESSAGES = {
    -9: "اطلاعات ارسالی به زرین‌پال نامعتبر است (مرچنت، مبلغ یا آدرس بازگشت).",
    -10: "مرچنت کد یا IP سرور در زرین‌پال معتبر نیست.",
    -11: "مرچنت کد زرین‌پال فعال نیست.",
    -12: "تلاش بیش از حد مجاز؛ کمی بعد دوباره تلاش کنید.",
    -15: "درگاه زرین‌پال تعلیق شده است.",
    -16: "سطح تأیید پذیرنده در زرین‌پال کافی نیست.",
    -50: "مبلغ پرداخت‌شده با مبلغ فاکتور یکسان نیست.",
    -51: "پرداخت انجام نشده یا ناموفق بوده است.",
    -52: "خطای غیرمنتظره در زرین‌پال؛ با پشتیبانی تماس بگیرید.",
    -53: "این پرداخت متعلق به این مرچنت کد نیست.",
    -54: "شناسه پرداخت (Authority) نامعتبر است.",
}


class ZarinpalError(Exception):
    """A Zarinpal API or flow error with a user-facing Persian message."""

    def __init__(self, message: str, code: int | None = None):
        super().__init__(message)
        self.message = message
        self.code = code


def status_label(status: str | None) -> str:
    return STATUS_LABELS.get(status or "", status or "نامشخص")


def payment_url(payment: ZarinpalPayment) -> str | None:
    return start_pay_url(payment.authority, payment.sandbox) if payment.authority else None


# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------


def _parse(data: Any) -> tuple[int | None, dict[str, Any], str | None]:
    """Return (code, data, error message) from Zarinpal's `{"data": ..., "errors": ...}` envelope."""
    if not isinstance(data, dict):
        return None, {}, None
    payload = data.get("data") if isinstance(data.get("data"), dict) else {}
    errors = data.get("errors")
    if isinstance(errors, dict) and errors.get("code") is not None:
        return _as_int(errors.get("code")), payload, str(errors.get("message") or "")
    return _as_int(payload.get("code")), payload, None


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except TypeError, ValueError:
        return None


class ZarinpalClient:
    def __init__(self, merchant_id: str, sandbox: bool, *, transport: httpx.AsyncBaseTransport | None = None):
        self.merchant_id = merchant_id
        self.sandbox = sandbox
        self._transport = transport

    async def _post(self, path: str, body: dict[str, Any]) -> tuple[int | None, dict[str, Any]]:
        if not self.merchant_id:
            raise ZarinpalError("مرچنت کد زرین‌پال تنظیم نشده است.")
        try:
            async with httpx.AsyncClient(
                base_url=base_url(self.sandbox), timeout=20.0, transport=self._transport
            ) as client:
                response = await client.post(path, json=body, headers={"Accept": "application/json"})
        except httpx.HTTPError as e:
            logger.error("Zarinpal request %s failed: %s", path, e)
            raise ZarinpalError("ارتباط با زرین‌پال برقرار نشد. کمی بعد دوباره تلاش کنید.") from e
        try:
            raw = response.json()
        except ValueError:
            raw = None
        code, payload, error_text = _parse(raw)
        if code is None:
            logger.warning("Zarinpal %s -> HTTP %s | body=%s", path, response.status_code, response.text[:500])
            raise ZarinpalError(f"پاسخ نامعتبر از زرین‌پال (HTTP {response.status_code}).")
        if error_text is not None:
            logger.warning("Zarinpal %s -> code %s: %s", path, code, error_text)
        return code, payload

    async def request_payment(self, *, amount_rial: int, description: str, callback: str, order_id: str) -> str:
        """Open a payment session and return its authority."""
        code, payload = await self._post(
            "/pg/v4/payment/request.json",
            {
                "merchant_id": self.merchant_id,
                "amount": int(amount_rial),
                "currency": "IRR",
                "description": description,
                "callback_url": callback,
                "metadata": {"order_id": order_id},
            },
        )
        authority = str(payload.get("authority") or "")
        if code != 100 or not authority:
            raise ZarinpalError(ERROR_MESSAGES.get(code or 0, f"خطای زرین‌پال (کد {code})."), code)
        return authority

    async def verify(self, *, amount_rial: int, authority: str) -> tuple[int | None, dict[str, Any]]:
        """Raw verify answer; callers decide what a non-success code means."""
        return await self._post(
            "/pg/v4/payment/verify.json",
            {"merchant_id": self.merchant_id, "amount": int(amount_rial), "authority": authority},
        )


def _client_for(payment: ZarinpalPayment, settings) -> ZarinpalClient:
    return ZarinpalClient(merchant_id_for(settings, payment.sandbox), payment.sandbox)


async def test_connection(merchant_id: str, sandbox: bool) -> tuple[bool, str]:
    """Open a throwaway 1,000-toman session; success proves the merchant id and server IP are accepted."""
    url = callback_url() or "https://example.com/zarinpal/callback"
    try:
        authority = await ZarinpalClient(merchant_id.strip(), sandbox).request_payment(
            amount_rial=10_000, description="Connection test", callback=url, order_id="ZP-TEST"
        )
    except ZarinpalError as e:
        return False, e.message
    mode = "تست (sandbox)" if sandbox else "واقعی"
    return True, f"اتصال برقرار است ({mode}). Authority: {authority[:12]}…"


# ---------------------------------------------------------------------------
# Deposit flow
# ---------------------------------------------------------------------------


async def create_deposit(user_id: int, amount: int, *, source: str) -> ZarinpalPayment:
    settings = await SettingsManager().get_settings()
    if not is_available_for(settings, user_id):
        raise ZarinpalError("درگاه زرین‌پال در حال حاضر فعال نیست.")
    min_amount, max_amount = deposit_limits(settings)
    if amount < min_amount or amount > max_amount:
        raise ZarinpalError(f"مبلغ باید بین {min_amount:,} تا {max_amount:,} تومان باشد.")
    crud = ZarinpalPaymentCRUD()
    if await crud.count_open_for_user(user_id) >= MAX_OPEN_PAYMENTS:
        raise ZarinpalError("بیش از سه پرداخت باز دارید. ابتدا آن‌ها را پرداخت کنید یا چند دقیقه صبر کنید.")
    callback = callback_url()
    if not callback:
        raise ZarinpalError("آدرس بازگشت (WEBAPP_URL با https) تنظیم نشده است.")

    sandbox = is_sandbox(settings)
    payment = await crud.create(user_id=user_id, amount=amount, sandbox=sandbox, source=source)
    try:
        authority = await ZarinpalClient(merchant_id_for(settings, sandbox), sandbox).request_payment(
            amount_rial=amount * 10,
            description=f"شارژ کیف پول کاربر {user_id} - {payment.order_id}",
            callback=callback,
            order_id=payment.order_id,
        )
    except ZarinpalError:
        await crud.delete(payment.id)
        raise
    payment = await crud.update(payment.id, authority=authority) or payment
    await send_log_message(
        LogType.CRYPTO,
        message=(
            f"#پرداخت_جدید_زرین‌پال{' 🧪 (تستی)' if sandbox else ''} ({'وب‌اپ' if source == 'webapp' else 'ربات'})\n"
            f"👤 شناسه کاربر: <code>{user_id}</code> | <a href='tg://user?id={user_id}'>پروفایل کاربر</a>\n"
            f"🧾 شناسه سفارش: <code>{payment.order_id}</code>\n"
            f"💵 مبلغ: <code>{amount:,}</code> تومان"
        ),
        parse_mode="html",
    )
    return payment


async def verify_payment(payment: ZarinpalPayment, *, buyer_canceled: bool = False) -> ZarinpalPayment:
    """Ask Zarinpal whether the payment went through and apply the answer (credit, close or keep waiting)."""
    if payment.status not in OPEN_STATUSES or not payment.authority:
        return payment
    crud = ZarinpalPaymentCRUD()
    settings = await SettingsManager().get_settings()
    expired = time.time() - int(payment.created_at or 0) > LOCAL_EXPIRY_SECONDS
    try:
        code, data = await _client_for(payment, settings).verify(
            amount_rial=int(payment.amount) * 10, authority=payment.authority
        )
    except ZarinpalError as e:
        logger.warning("Zarinpal verify failed for %s: %s", payment.order_id, e.message)
        if expired:
            return await _close_payment(payment, "expired")
        await crud.update(payment.id)  # bump updated_at so the poller rotates to other payments
        return payment

    if code in SUCCESS_CODES:
        return await _credit_payment(payment, ref_id=data.get("ref_id"), card_pan=data.get("card_pan"))
    if code == CODE_NOT_PAID and buyer_canceled:
        return await _close_payment(payment, "canceled")
    if code in (-50, -53, -54):
        # Amount mismatch or a foreign/invalid authority can never succeed later.
        logger.error("Zarinpal verify for %s returned %s; closing as failed", payment.order_id, code)
        return await _close_payment(payment, "failed")
    if expired:
        return await _close_payment(payment, "expired")
    await crud.update(payment.id)
    return payment


async def handle_callback(authority: str, status: str) -> ZarinpalPayment | None:
    """Buyer returned from Zarinpal. The query string is untrusted: the result always comes from verify."""
    payment = await ZarinpalPaymentCRUD().get_by_authority(authority)
    if not payment:
        return None
    return await verify_payment(payment, buyer_canceled=(status or "").upper() != "OK")


# ---------------------------------------------------------------------------
# Crediting and notifications
# ---------------------------------------------------------------------------


async def _notify_user(payment: ZarinpalPayment, text: str, buttons=None) -> None:
    try:
        await Kenzo.send_message(payment.user_id, text, parse_mode="html", buttons=buttons)
    except Exception as e:
        logger.warning("Zarinpal user notify failed for %s: %s", payment.user_id, e)


async def _credit_payment(payment: ZarinpalPayment, *, ref_id: Any, card_pan: Any) -> ZarinpalPayment:
    settings = await SettingsManager().get_settings()
    percent = bonus_percent(settings)
    bonus = await calculate_payment_bonus(amount=int(payment.amount), bonus_enabled=percent > 0, bonus_percent=percent)
    total_amount = int(payment.amount) + bonus
    crud = ZarinpalPaymentCRUD()
    approved = await crud.approve_and_credit(
        payment.id,
        total_amount,
        ref_id=str(ref_id) if ref_id is not None else None,
        card_pan=str(card_pan)[:32] if card_pan else None,
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
                f"🎉 <b>پرداخت زرین‌پال با موفقیت انجام شد!</b>{test_tag}\n\n"
                f"🧾 <b>کد پیگیری:</b> <code>{payment.ref_id or '—'}</code>\n"
                f"💵 <b>مبلغ شارژ:</b> <code>{int(payment.amount):,}</code> تومان\n"
                f"{bonus_line}"
                f"💳 <b>موجودی جدید:</b> <code>{new_balance:,}</code> تومان\n\n"
                f"<code>#Zarinpal_{payment.order_id}</code>",
                buttons=balance_btn,
            )
        await send_log_message(
            LogType.CRYPTO,
            message=(
                f"#پرداخت_زرین‌پال{test_tag}\n<b>✅ پرداخت زرین‌پال کاربر تأیید شد</b>\n\n"
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
        logger.error("Zarinpal post-credit notification failed for %s: %s", payment.order_id, e)
    return payment


async def _close_payment(payment: ZarinpalPayment, status: str) -> ZarinpalPayment:
    closed = await ZarinpalPaymentCRUD().close_if_open(payment.id, status)
    if not closed:
        return await ZarinpalPaymentCRUD().get(payment.id) or payment
    payment = closed
    await cancel_after_crypto_expire(int(payment.id))
    await _notify_user(
        payment,
        "<b>#اطلاع_رسانی</b>\n\n"
        f"<b>📅 پرداخت زرین‌پال</b> <code>{payment.order_id}</code> <b>{status_label(status)}.</b>\n"
        f"<b>💵 مبلغ:</b> <code>{int(payment.amount):,}</code> <b>تومان</b>\n"
        "اگر مبلغی از حساب شما کسر شده، طبق قوانین بانکی حداکثر تا ۷۲ ساعت به حساب‌تان برمی‌گردد.",
        buttons=[[Button.inline(text=f"🚫 {status_label(status)}", data="no_action")]],
    )
    await send_log_message(
        LogType.CRYPTO,
        message=(
            f"#پرداخت_زرین‌پال_بسته_شد{' 🧪' if payment.sandbox else ''}\n"
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
    "ZarinpalClient",
    "ZarinpalError",
    "create_deposit",
    "handle_callback",
    "is_ready",
    "payment_url",
    "status_label",
    "test_connection",
    "verify_payment",
]
