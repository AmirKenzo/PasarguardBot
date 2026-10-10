"""The one deposit flow shared by every Iranian direct gateway (bot, web app, callback page and poller).

Flow: request -> buyer pays on the gateway's page -> the gateway sends the buyer back to our callback
-> we verify. Only the provider's verify answer ("paid") credits the user, and crediting is one atomic
DB transaction, so the callback, the bot "check" button and the poller can all race safely.

Test mode (per gateway) talks to the provider's sandbox / test merchant and is only offered to admins.
"""

from __future__ import annotations

import time
from collections.abc import Mapping

from telethon import Button

from app import Kenzo
from app.db.crud.ir_gateway_payments import OPEN_STATUSES, IrGatewayPaymentCRUD
from app.db.crud.settings import SettingsManager
from app.db.models.ir_gateway_payment import IrGatewayPayment
from app.logger import LogType, get_logger
from app.services.billing.direct_pay_fulfillment import (
    cancel_after_crypto_expire,
    try_fulfill_after_crypto_credit,
)
from app.services.billing.payment_bonus import calculate_payment_bonus
from app.services.payments.ir_gateways import config
from app.services.payments.ir_gateways.providers import GATEWAYS, GatewayError, get_provider
from app.telegram.shared.utils.logging import send_log_message

logger = get_logger(__name__)

MAX_OPEN_PAYMENTS = 3
# A payment the gateway still reports unpaid after this long is closed locally.
LOCAL_EXPIRY_SECONDS = 30 * 60

STATUS_LABELS = {
    "pending": "در انتظار پرداخت",
    "completed": "پرداخت شده",
    "failed": "ناموفق",
    "canceled": "لغو شده",
    "expired": "منقضی شده",
}


def status_label(status: str | None) -> str:
    return STATUS_LABELS.get(status or "", status or "نامشخص")


def gateway_title(key: str) -> str:
    provider = GATEWAYS.get(key)
    return provider.title if provider else key


def payment_url(payment: IrGatewayPayment) -> str | None:
    provider = GATEWAYS.get(payment.gateway)
    if not provider or not payment.authority:
        return None
    return provider.start_pay_url(payment.authority, payment.sandbox)


async def test_connection(key: str, merchant: str, sandbox: bool) -> tuple[bool, str]:
    """Open a throwaway 1,000-toman payment; success proves the merchant and server IP are accepted."""
    provider = get_provider(key)
    try:
        authority = await provider.request_payment(
            merchant=provider.merchant_for(merchant.strip(), sandbox),
            sandbox=sandbox,
            amount_rial=10_000,
            description="Connection test",
            callback=config.callback_url(key) or "https://example.com/callback",
            order_id=f"{provider.order_prefix}-TEST",
        )
    except GatewayError as e:
        return False, e.message
    mode = "تست" if sandbox else "واقعی"
    return True, f"اتصال برقرار است ({mode}). شناسه: {authority[:16]}"


# ---------------------------------------------------------------------------
# Deposit flow
# ---------------------------------------------------------------------------


async def create_deposit(key: str, user_id: int, amount: int, *, source: str) -> IrGatewayPayment:
    provider = get_provider(key)
    settings = await SettingsManager().get_settings()
    if not config.is_available_for(settings, key, user_id):
        raise GatewayError(f"درگاه {provider.title} در حال حاضر فعال نیست.")
    min_amount, max_amount = config.deposit_limits(settings, key)
    if amount < min_amount or amount > max_amount:
        raise GatewayError(f"مبلغ باید بین {min_amount:,} تا {max_amount:,} تومان باشد.")
    crud = IrGatewayPaymentCRUD()
    if await crud.count_open_for_user(user_id) >= MAX_OPEN_PAYMENTS:
        raise GatewayError("بیش از سه پرداخت باز دارید. ابتدا آن‌ها را پرداخت کنید یا چند دقیقه صبر کنید.")
    callback = config.callback_url(key)
    if not callback:
        raise GatewayError("آدرس بازگشت (WEBAPP_URL با https) تنظیم نشده است.")

    sandbox = config.is_sandbox(settings, key)
    payment = await crud.create(
        gateway=key, order_prefix=provider.order_prefix, user_id=user_id, amount=amount, sandbox=sandbox, source=source
    )
    try:
        authority = await provider.request_payment(
            merchant=config.merchant_for(settings, key, sandbox),
            sandbox=sandbox,
            amount_rial=amount * 10,
            description=f"شارژ کیف پول کاربر {user_id} - {payment.order_id}",
            callback=callback,
            order_id=payment.order_id,
        )
    except GatewayError:
        await crud.delete(payment.id)
        raise
    payment = await crud.update(payment.id, authority=authority) or payment
    await send_log_message(
        LogType.CRYPTO,
        message=(
            f"#پرداخت_جدید_{provider.title.replace(' ', '_')}{' 🧪 (تستی)' if sandbox else ''} "
            f"({'وب‌اپ' if source == 'webapp' else 'ربات'})\n"
            f"👤 شناسه کاربر: <code>{user_id}</code> | <a href='tg://user?id={user_id}'>پروفایل کاربر</a>\n"
            f"🧾 شناسه سفارش: <code>{payment.order_id}</code>\n"
            f"💵 مبلغ: <code>{amount:,}</code> تومان"
        ),
        parse_mode="html",
    )
    return payment


async def verify_payment(payment: IrGatewayPayment, *, buyer_canceled: bool = False) -> IrGatewayPayment:
    """Ask the gateway whether the payment went through and apply the answer (credit, close or keep waiting)."""
    if payment.status not in OPEN_STATUSES or not payment.authority:
        return payment
    provider = GATEWAYS.get(payment.gateway)
    if provider is None:
        logger.error("Payment %s belongs to unknown gateway %r", payment.order_id, payment.gateway)
        return payment
    crud = IrGatewayPaymentCRUD()
    settings = await SettingsManager().get_settings()
    expired = time.time() - int(payment.created_at or 0) > LOCAL_EXPIRY_SECONDS
    try:
        result = await provider.verify(
            merchant=config.merchant_for(settings, payment.gateway, payment.sandbox),
            sandbox=payment.sandbox,
            authority=payment.authority,
            amount_rial=int(payment.amount) * 10,
            order_id=payment.order_id,
        )
    except GatewayError as e:
        logger.warning("%s verify failed for %s: %s", payment.gateway, payment.order_id, e.message)
        if expired:
            return await _close_payment(payment, "expired")
        await crud.update(payment.id)  # bump updated_at so the poller rotates to other payments
        return payment

    if result.outcome == "paid":
        return await _credit_payment(payment, ref_id=result.ref_id, card_pan=result.card_pan)
    if result.outcome == "failed":
        logger.error(
            "%s verify for %s can never succeed (%s); closing", payment.gateway, payment.order_id, result.detail
        )
        return await _close_payment(payment, "failed")
    if buyer_canceled:
        return await _close_payment(payment, "canceled")
    if expired:
        return await _close_payment(payment, "expired")
    await crud.update(payment.id)
    return payment


async def handle_callback(key: str, query: Mapping[str, str]) -> IrGatewayPayment | None:
    """Buyer returned from the gateway. The query string is untrusted: the result always comes from verify."""
    authority, buyer_canceled = get_provider(key).parse_callback(query)
    if not authority:
        return None
    payment = await IrGatewayPaymentCRUD().get_by_authority(key, authority)
    if not payment:
        return None
    return await verify_payment(payment, buyer_canceled=buyer_canceled)


# ---------------------------------------------------------------------------
# Crediting and notifications
# ---------------------------------------------------------------------------


async def _notify_user(payment: IrGatewayPayment, text: str, buttons=None) -> None:
    try:
        await Kenzo.send_message(payment.user_id, text, parse_mode="html", buttons=buttons)
    except Exception as e:
        logger.warning("Gateway user notify failed for %s: %s", payment.user_id, e)


async def _credit_payment(payment: IrGatewayPayment, *, ref_id: str | None, card_pan: str | None) -> IrGatewayPayment:
    settings = await SettingsManager().get_settings()
    percent = config.bonus_percent(settings, payment.gateway)
    bonus = await calculate_payment_bonus(amount=int(payment.amount), bonus_enabled=percent > 0, bonus_percent=percent)
    total_amount = int(payment.amount) + bonus
    crud = IrGatewayPaymentCRUD()
    approved = await crud.approve_and_credit(
        payment.id,
        total_amount,
        ref_id=str(ref_id)[:64] if ref_id else None,
        card_pan=str(card_pan)[:32] if card_pan else None,
    )
    if not approved:
        return await crud.get(payment.id) or payment
    payment, new_balance = approved

    title = gateway_title(payment.gateway)
    test_tag = " 🧪 (تستی)" if payment.sandbox else ""
    balance_btn = [[Button.inline(text=f"💳 موجودی: {new_balance:,} تومان", data="no_action")]]
    bonus_line = f"🎁 <b>بونوس:</b> +<code>{bonus:,}</code> تومان ({percent}%)\n" if bonus > 0 else ""
    try:
        if not await try_fulfill_after_crypto_credit(int(payment.id)):
            await _notify_user(
                payment,
                f"🎉 <b>پرداخت {title} با موفقیت انجام شد!</b>{test_tag}\n\n"
                f"🧾 <b>کد پیگیری:</b> <code>{payment.ref_id or '—'}</code>\n"
                f"💵 <b>مبلغ شارژ:</b> <code>{int(payment.amount):,}</code> تومان\n"
                f"{bonus_line}"
                f"💳 <b>موجودی جدید:</b> <code>{new_balance:,}</code> تومان\n\n"
                f"<code>#{payment.gateway}_{payment.order_id}</code>",
                buttons=balance_btn,
            )
        await send_log_message(
            LogType.CRYPTO,
            message=(
                f"#پرداخت_{title.replace(' ', '_')}{test_tag}\n<b>✅ پرداخت {title} کاربر تأیید شد</b>\n\n"
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
        logger.error("Gateway post-credit notification failed for %s: %s", payment.order_id, e)
    return payment


async def _close_payment(payment: IrGatewayPayment, status: str) -> IrGatewayPayment:
    crud = IrGatewayPaymentCRUD()
    closed = await crud.close_if_open(payment.id, status)
    if not closed:
        return await crud.get(payment.id) or payment
    payment = closed
    title = gateway_title(payment.gateway)
    await cancel_after_crypto_expire(int(payment.id))
    await _notify_user(
        payment,
        "<b>#اطلاع_رسانی</b>\n\n"
        f"<b>📅 پرداخت {title}</b> <code>{payment.order_id}</code> <b>{status_label(status)}.</b>\n"
        f"<b>💵 مبلغ:</b> <code>{int(payment.amount):,}</code> <b>تومان</b>\n"
        "اگر مبلغی از حساب شما کسر شده، طبق قوانین بانکی حداکثر تا ۷۲ ساعت به حساب‌تان برمی‌گردد.",
        buttons=[[Button.inline(text=f"🚫 {status_label(status)}", data="no_action")]],
    )
    await send_log_message(
        LogType.CRYPTO,
        message=(
            f"#پرداخت_{title.replace(' ', '_')}_بسته_شد{' 🧪' if payment.sandbox else ''}\n"
            f"👤 شناسه کاربر: <code>{payment.user_id}</code>\n"
            f"🧾 شناسه سفارش: <code>{payment.order_id}</code>\n"
            f"💵 مبلغ: <code>{int(payment.amount):,}</code> تومان\n"
            f"📌 وضعیت: {status_label(status)}"
        ),
        parse_mode="html",
    )
    return payment
