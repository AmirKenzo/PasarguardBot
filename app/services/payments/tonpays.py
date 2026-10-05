"""TonPays gateway: API client plus the shared deposit flow used by the bot, the web app, the webhook and the job.

Two modes (picked per invoice when it is created):
- standard: the buyer pays inside @TonPaysInvoiceBot / the TonPays web page;
- custom:   the card is shown inside this bot and the buyer's receipt is forwarded to TonPays.

The webhook body is never trusted on its own: every status change is re-read from the
TonPays check endpoint before crediting, and crediting is a single atomic DB transaction.
"""

from __future__ import annotations

import hmac
import time
from typing import Any

import httpx
from telethon import Button

from app import Kenzo
from app.db.crud.settings import SettingsManager
from app.db.crud.tonpays_invoices import OPEN_STATUSES, TonPaysInvoiceCRUD
from app.db.models.tonpays_invoice import TonPaysInvoice
from app.logger import LogType, get_logger
from app.services.billing.direct_pay_fulfillment import (
    cancel_after_crypto_expire,
    try_fulfill_after_crypto_credit,
)
from app.services.billing.payment_bonus import calculate_payment_bonus
from app.services.payments.tonpays_config import (
    MODE_CUSTOM,
    MODE_STANDARD,
    api_key_for,
    callback_url,
    deposit_limits,
    gateway_mode,
    is_ready,
)
from app.telegram.shared.utils.logging import send_log_message

logger = get_logger(__name__)

BASE_URL = "https://tonpays.online"
MAX_OPEN_INVOICES = 3
# Invoices TonPays still reports as open after this long are closed locally.
LOCAL_EXPIRY_SECONDS = 24 * 60 * 60
RECEIPT_MAX_BYTES = 10 * 1024 * 1024

STATUS_LABELS = {
    "pending": "در انتظار پرداخت",
    "processing": "در انتظار تأیید",
    "completed": "تأیید شده",
    "need_action": "نیاز به اقدام",
    "rejected": "رد شده",
    "expired": "منقضی شده",
    "canceled": "لغو شده",
}

ERROR_MESSAGES = {
    "MISSING_API_KEY": "کلید API درگاه TonPays تنظیم نشده است.",
    "INVALID_API_KEY": "کلید API درگاه TonPays نامعتبر است.",
    "INACTIVE_API_KEY": "کلید API درگاه TonPays غیرفعال است.",
    "WRONG_API_KEY_KIND": "نوع کلید API با نوع درگاه انتخاب‌شده هم‌خوانی ندارد.",
    "ACCOUNT_NOT_VERIFIED": "حساب TonPays هنوز تأیید نشده است.",
    "ACCOUNT_SUSPENDED": "حساب TonPays تعلیق شده است.",
    "STORE_INACTIVE": "فروشگاه در TonPays غیرفعال است.",
    "GATEWAY_NOT_APPROVED": "درگاه کاستوم TonPays هنوز تأیید نشده است.",
    "DUPLICATE_ORDER_ID": "شناسه سفارش تکراری است، دوباره تلاش کنید.",
    "AMOUNT_TOO_LOW": "مبلغ کمتر از حداقل مجاز TonPays است.",
    "AMOUNT_TOO_HIGH": "مبلغ بیشتر از حداکثر مجاز TonPays است.",
    "INVALID_BUYER_CHAT_ID": "شناسه تلگرام خریدار نامعتبر است.",
    "INVALID_CALLBACK_URL": "آدرس وب‌هوک TonPays نامعتبر است.",
    "INVALID_RECEIPT_TYPE": "فایل فیش باید تصویر باشد.",
    "RECEIPT_TOO_LARGE": "حجم فیش حداکثر ۱۰ مگابایت است.",
    "RATE_LIMIT_EXCEEDED": "درخواست‌ها زیاد است، کمی بعد دوباره تلاش کنید.",
    "INVOICE_NOT_FOUND": "فاکتور در TonPays پیدا نشد.",
    "ACCESS_DENIED": "دسترسی به این فاکتور مجاز نیست.",
}


class TonPaysError(Exception):
    """A TonPays API or flow error with a user-facing Persian message."""

    def __init__(self, message: str, code: str | None = None, status: int | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def status_label(status: str | None) -> str:
    return STATUS_LABELS.get(status or "", status or "نامشخص")


# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------


def _parse_error(data: dict[str, Any]) -> tuple[str | None, str | None]:
    """Read the error code/message from either the documented `detail` or the live `error` envelope."""
    for field in ("error", "detail"):
        value = data.get(field)
        if isinstance(value, dict):
            return value.get("code"), value.get("message")
        if isinstance(value, str):
            return None, value
        if isinstance(value, list) and value:
            first = value[0]
            return None, first.get("msg") if isinstance(first, dict) else str(first)
    return None, data.get("message") if isinstance(data.get("message"), str) else None


class TonPaysClient:
    def __init__(self, api_key: str, mode: str):
        self.api_key = api_key
        self.mode = mode

    async def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        if not self.api_key:
            raise TonPaysError(ERROR_MESSAGES["MISSING_API_KEY"], "MISSING_API_KEY")
        try:
            async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
                response = await client.request(method, path, headers={"X-API-Key": self.api_key}, **kwargs)
        except httpx.HTTPError as e:
            logger.error("TonPays request %s %s failed: %s", method, path, e)
            raise TonPaysError("ارتباط با درگاه TonPays برقرار نشد. کمی بعد دوباره تلاش کنید.") from e
        try:
            data = response.json()
        except ValueError:
            data = {}
        if not isinstance(data, dict):
            data = {}
        if response.status_code >= 400 or data.get("success") is False:
            code, text = _parse_error(data)
            if code is None and response.status_code == 404:
                code = "INVOICE_NOT_FOUND"
            logger.warning(
                "TonPays %s %s -> %s %s %s | body=%s",
                method,
                path,
                response.status_code,
                code,
                text,
                response.text[:500],
            )
            fallback = f"خطا در درگاه TonPays (HTTP {response.status_code}{f': {text}' if text else ''})."
            raise TonPaysError(ERROR_MESSAGES.get(code or "", fallback), code, response.status_code)
        # Live API wraps errors as {"success": false, "error": {...}}; accept a {"data": {...}} success wrapper too.
        payload = data.get("data")
        return payload if isinstance(payload, dict) and "invoice_id" not in data else data

    async def create_invoice(self, *, amount: int, order_id: str, buyer_chat_id: int) -> dict[str, Any]:
        body: dict[str, Any] = {"amount": int(amount), "order_id": order_id, "buyer_chat_id": int(buyer_chat_id)}
        url = callback_url()
        if url:
            body["callback_url"] = url
        path = "/api/custom/v1/invoices/telegram/create" if self.mode == MODE_CUSTOM else "/api/v1/invoices/create"
        # Optional fields TonPays may reject; drop the rejected one and retry once (the poller covers a missing webhook).
        optional = {"INVALID_CALLBACK_URL": "callback_url"}
        if self.mode == MODE_STANDARD:
            optional["INVALID_BUYER_CHAT_ID"] = "buyer_chat_id"
        try:
            return await self._request("POST", path, json=body)
        except TonPaysError as e:
            field = optional.get(e.code or "")
            if not field or field not in body:
                raise
            logger.warning("TonPays rejected %s (%s); retrying without it", field, e.code)
            body.pop(field)
            return await self._request("POST", path, json=body)

    async def check(self, invoice_id: str) -> dict[str, Any]:
        prefix = "/api/custom/v1" if self.mode == MODE_CUSTOM else "/api/v1"
        return await self._request("GET", f"{prefix}/invoices/check/{invoice_id}")

    async def change_card(self, invoice_id: str) -> dict[str, Any]:
        return await self._request("POST", f"/api/custom/v1/invoices/{invoice_id}/change-card")

    async def upload_receipt(self, invoice_id: str, content: bytes, filename: str, content_type: str) -> dict[str, Any]:
        files = {"file": (filename or "receipt.jpg", content, content_type or "image/jpeg")}
        return await self._request("POST", f"/api/custom/v1/invoices/{invoice_id}/receipt", files=files)


async def _client_for(invoice: TonPaysInvoice) -> TonPaysClient:
    settings = await SettingsManager().get_settings()
    return TonPaysClient(api_key_for(settings, invoice.mode), invoice.mode)


async def test_connection(api_key: str, mode: str) -> tuple[bool, str]:
    """Probe a key with a lookup of a non-existent invoice: INVOICE_NOT_FOUND means the key works."""
    try:
        await TonPaysClient(api_key.strip(), mode).check("TP-CONNECTIONTEST")
        return True, "اتصال برقرار است."
    except TonPaysError as e:
        if e.code in ("INVOICE_NOT_FOUND", "ACCESS_DENIED"):
            return True, "اتصال برقرار است و کلید معتبر است."
        return False, e.message


# ---------------------------------------------------------------------------
# Deposit flow
# ---------------------------------------------------------------------------


async def create_deposit(user_id: int, amount: int, *, source: str) -> TonPaysInvoice:
    settings = await SettingsManager().get_settings()
    if not is_ready(settings):
        raise TonPaysError("درگاه TonPays در حال حاضر فعال نیست.")
    min_amount, max_amount = deposit_limits(settings)
    if amount < min_amount or amount > max_amount:
        raise TonPaysError(f"مبلغ باید بین {min_amount:,} تا {max_amount:,} تومان باشد.")
    crud = TonPaysInvoiceCRUD()
    if await crud.count_open_for_user(user_id) >= MAX_OPEN_INVOICES:
        raise TonPaysError(
            "بیش از سه فاکتور باز دارید. ابتدا فاکتورهای قبلی را پرداخت کنید یا منتظر انقضای آن‌ها بمانید."
        )

    mode = gateway_mode(settings)
    invoice = await crud.create(user_id=user_id, amount=amount, mode=mode, source=source)
    try:
        data = await TonPaysClient(api_key_for(settings, mode), mode).create_invoice(
            amount=amount, order_id=invoice.order_id, buyer_chat_id=user_id
        )
    except TonPaysError:
        await crud.delete(invoice.id)
        raise
    invoice = await crud.update(
        invoice.id,
        invoice_id=data.get("invoice_id"),
        final_amount=int(data.get("final_amount") or amount),
        status=str(data.get("status") or "pending"),
        invoice_url=data.get("invoice_url"),
        web_invoice_url=data.get("web_invoice_url"),
        card_number=data.get("card_number"),
        card_name=data.get("card_name"),
    )
    await send_log_message(
        LogType.CRYPTO,
        message=(
            f"#فاکتور_جدید_TonPays ({'وب‌اپ' if source == 'webapp' else 'ربات'})\n"
            f"👤 شناسه کاربر: <code>{user_id}</code> | <a href='tg://user?id={user_id}'>پروفایل کاربر</a>\n"
            f"💡 شماره فاکتور: <code>{invoice.invoice_id}</code>\n"
            f"💵 مبلغ: <code>{amount:,}</code> تومان | مبلغ پرداختی: <code>{int(invoice.final_amount or 0):,}</code>\n"
            f"🧬 نوع درگاه: {'کاستوم' if mode == MODE_CUSTOM else 'معمولی'}"
        ),
        parse_mode="html",
    )
    return invoice


async def refresh_invoice(invoice: TonPaysInvoice) -> TonPaysInvoice:
    """Re-read the invoice from TonPays and apply the result (credit, close or keep waiting)."""
    if invoice.status not in OPEN_STATUSES or not invoice.invoice_id:
        return invoice
    crud = TonPaysInvoiceCRUD()
    try:
        data = await (await _client_for(invoice)).check(invoice.invoice_id)
    except TonPaysError as e:
        logger.warning("TonPays check failed for %s: %s", invoice.invoice_id, e.message)
        if time.time() - int(invoice.created_at or 0) > LOCAL_EXPIRY_SECONDS:
            return await _close_invoice(invoice, "expired")
        await crud.update(invoice.id)  # bump updated_at so the poller rotates to other invoices
        return invoice

    status = str(data.get("status") or invoice.status)
    if data.get("final_amount"):
        invoice = await crud.update(invoice.id, final_amount=int(data["final_amount"])) or invoice
    if status == "completed" and data.get("paid") is True:
        return await _credit_invoice(invoice)
    if status not in OPEN_STATUSES:
        return await _close_invoice(invoice, status)
    if time.time() - int(invoice.created_at or 0) > LOCAL_EXPIRY_SECONDS:
        return await _close_invoice(invoice, "expired")
    if status != invoice.status:
        previous = invoice.status
        invoice = await crud.update(invoice.id, status=status) or invoice
        if status == "need_action" and previous != "need_action":
            await _notify_user(
                invoice,
                f"⚠️ <b>فاکتور TonPays شماره</b> <code>{invoice.invoice_id}</code> <b>نیاز به اقدام دارد.</b>\n"
                "لطفاً فیش واریزی را بررسی کنید یا با پشتیبانی تماس بگیرید.",
            )
    else:
        await crud.update(invoice.id)
    return invoice


async def refresh_by_invoice_id(invoice_id: str) -> None:
    invoice = await TonPaysInvoiceCRUD().get_by_invoice_id(invoice_id)
    if invoice:
        await refresh_invoice(invoice)


async def change_card(invoice: TonPaysInvoice) -> dict[str, Any]:
    if invoice.mode != MODE_CUSTOM or invoice.status not in OPEN_STATUSES or not invoice.invoice_id:
        raise TonPaysError("تعویض کارت برای این فاکتور ممکن نیست.")
    data = await (await _client_for(invoice)).change_card(invoice.invoice_id)
    await TonPaysInvoiceCRUD().update(
        invoice.id,
        card_number=data.get("card_number") or invoice.card_number,
        card_name=data.get("card_name") or invoice.card_name,
        final_amount=int(data.get("final_amount") or invoice.final_amount or invoice.amount),
    )
    return data


async def submit_receipt(invoice: TonPaysInvoice, content: bytes, filename: str, content_type: str) -> TonPaysInvoice:
    if invoice.mode != MODE_CUSTOM or invoice.status not in OPEN_STATUSES or not invoice.invoice_id:
        raise TonPaysError("ارسال فیش برای این فاکتور ممکن نیست.")
    if not content or len(content) > RECEIPT_MAX_BYTES:
        raise TonPaysError(ERROR_MESSAGES["RECEIPT_TOO_LARGE"])
    data = await (await _client_for(invoice)).upload_receipt(invoice.invoice_id, content, filename, content_type)
    return (
        await TonPaysInvoiceCRUD().update(invoice.id, receipt_sent=True, status=str(data.get("status") or "processing"))
        or invoice
    )


def verify_webhook_key(received: str | None, settings) -> bool:
    if not received:
        return False
    for mode in (MODE_STANDARD, MODE_CUSTOM):
        expected = api_key_for(settings, mode)
        if expected and hmac.compare_digest(received.strip(), expected):
            return True
    return False


# ---------------------------------------------------------------------------
# Crediting and notifications
# ---------------------------------------------------------------------------


async def _notify_user(invoice: TonPaysInvoice, text: str, buttons=None) -> None:
    try:
        await Kenzo.send_message(invoice.user_id, text, parse_mode="html", buttons=buttons)
    except Exception as e:
        logger.warning("TonPays user notify failed for %s: %s", invoice.user_id, e)


async def _credit_invoice(invoice: TonPaysInvoice) -> TonPaysInvoice:
    settings = await SettingsManager().get_settings()
    bonus = await calculate_payment_bonus(
        amount=int(invoice.amount),
        bonus_enabled=bool(getattr(settings, "tonpays_bonus_enabled", False)),
        bonus_percent=int(getattr(settings, "tonpays_bonus_percent", 0) or 0),
    )
    total_amount = int(invoice.amount) + bonus
    approved = await TonPaysInvoiceCRUD().approve_and_credit(invoice.id, total_amount)
    if not approved:
        return await TonPaysInvoiceCRUD().get(invoice.id) or invoice
    invoice, new_balance = approved

    balance_btn = [[Button.inline(text=f"💳 موجودی: {new_balance:,} تومان", data="no_action")]]
    bonus_line = (
        f"🎁 <b>بونوس:</b> +<code>{bonus:,}</code> تومان ({settings.tonpays_bonus_percent}%)\n" if bonus > 0 else ""
    )
    try:
        if not await try_fulfill_after_crypto_credit(int(invoice.id)):
            await _notify_user(
                invoice,
                "🎉 <b>پرداخت شما با موفقیت انجام شد!</b>\n\n"
                f"📋 <b>شماره فاکتور:</b> <code>{invoice.invoice_id}</code>\n"
                f"💵 <b>مبلغ شارژ:</b> <code>{int(invoice.amount):,}</code> تومان\n"
                f"{bonus_line}"
                f"💳 <b>موجودی جدید:</b> <code>{new_balance:,}</code> تومان\n\n"
                f"<code>#TonPays_{invoice.order_id}</code>",
                buttons=balance_btn,
            )
        await send_log_message(
            LogType.CRYPTO,
            message=(
                "#فاکتور_TonPays\n<b>✅ فاکتور TonPays کاربر پرداخت شد</b>\n\n"
                f"<b>👤 شناسه کاربری:</b> <code>{invoice.user_id}</code> | "
                f"<a href='tg://user?id={invoice.user_id}'>پروفایل کاربر</a>\n"
                f"<b>📋 شماره فاکتور:</b> <code>{invoice.invoice_id}</code>\n"
                f"<b>🧾 شناسه سفارش:</b> <code>{invoice.order_id}</code>\n"
                f"<b>💵 مبلغ شارژ:</b> <code>{int(invoice.amount):,}</code> تومان\n"
                f"<b>💰 مبلغ پرداختی کاربر:</b> <code>{int(invoice.final_amount or 0):,}</code> تومان\n"
                f"{bonus_line}"
                f"<b>💳 موجودی جدید کاربر:</b> <code>{new_balance:,}</code> تومان\n"
                f"<b>🧬 نوع درگاه:</b> {'کاستوم' if invoice.mode == MODE_CUSTOM else 'معمولی'}"
            ),
            parse_mode="html",
            buttons=balance_btn,
        )
    except Exception as e:
        logger.error("TonPays post-credit notification failed for %s: %s", invoice.order_id, e)
    return invoice


async def _close_invoice(invoice: TonPaysInvoice, status: str) -> TonPaysInvoice:
    invoice = await TonPaysInvoiceCRUD().update(invoice.id, status=status) or invoice
    await cancel_after_crypto_expire(int(invoice.id))
    await _notify_user(
        invoice,
        "<b>#اطلاع_رسانی</b>\n\n"
        f"<b>📅 فاکتور TonPays شماره</b> <code>{invoice.invoice_id}</code> <b>{status_label(status)}.</b>\n"
        f"<b>💵 مبلغ فاکتور:</b> <code>{int(invoice.amount):,}</code> <b>تومان</b>\n"
        "در صورت نیاز می‌توانید فاکتور جدید بسازید.",
        buttons=[[Button.inline(text=f"🚫 {status_label(status)}", data="no_action")]],
    )
    await send_log_message(
        LogType.CRYPTO,
        message=(
            "#فاکتور_TonPays_بسته_شد\n"
            f"👤 شناسه کاربر: <code>{invoice.user_id}</code>\n"
            f"💡 شماره فاکتور: <code>{invoice.invoice_id}</code>\n"
            f"💵 مبلغ: <code>{int(invoice.amount):,}</code> تومان\n"
            f"📌 وضعیت: {status_label(status)}"
        ),
        parse_mode="html",
    )
    return invoice
