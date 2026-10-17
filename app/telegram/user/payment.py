"""Telegram Stars payments: invoices, pre-checkout validation and successful payments."""

import math
import time

from telethon import Button, events, functions, types

from app import Kenzo
from app.db.crud.settings import SettingsManager
from app.db.crud.stars_transactions import StarsTransactionCRUD
from app.db.models.stars_transaction import StarsTransaction
from app.jobs.payments.stars import STARS_INVOICE_TTL_SECONDS
from app.logger import LogType, get_logger
from app.services.billing.payment_bonus import calculate_payment_bonus
from app.services.send_queue import enqueue
from app.telegram.keyboards.home import bhome_buttons
from app.telegram.plugins import PluginContext

MODULE_NAME = "user.payment"
MODULE_REQUIRED = True
MODULE_DESCRIPTION = "Telegram Stars payment flow"


def stars_precheckout_ok(tx, *, now: int) -> bool:
    """True only when Telegram should be told success=True."""
    if tx is None:
        return False
    if getattr(tx, "status", None) != "pending":
        return False
    created = int(getattr(tx, "created_at", 0) or 0)
    return created + STARS_INVOICE_TTL_SECONDS > now


STAR_USD_PRICE = 0.015


async def calculate_star_amount(usd_price: int, amount_in_toman: int) -> int:
    """Calculate the number of stars based on toman amount and USD price."""
    toman_per_star = usd_price * STAR_USD_PRICE
    stars = amount_in_toman / toman_per_star
    return max(1, math.ceil(stars))


async def _build_star_invoice(user_id: int, amount: int) -> tuple[StarsTransaction, types.InputMediaInvoice, int]:
    """Create Stars DB row + Telegram invoice media shared by chat and Mini App flows."""
    settings = await SettingsManager().get_settings()
    stars = await calculate_star_amount(int(settings.arz_usd), amount)

    tx = await StarsTransactionCRUD().create(user_id=user_id, amount=amount, stars=stars)

    invoice = types.Invoice(
        currency="XTR",
        prices=[types.LabeledPrice(label="پرداخت با استارز", amount=stars)],
        test=False,
        name_requested=False,
        phone_requested=False,
        email_requested=False,
        shipping_address_requested=False,
        flexible=False,
        phone_to_provider=False,
        email_to_provider=False,
    )

    payload = f"stars:{tx.id}"
    media = types.InputMediaInvoice(
        title="افزایش موجودی",
        description="برای شارژ حساب تعداد ستاره های زیر را پرداخت کنید.",
        invoice=invoice,
        payload=payload.encode("utf-8"),
        provider="",
        provider_data=types.DataJSON("{}"),
        start_param="stars-pay",
    )
    return tx, media, stars


async def send_star_invoice(user_id: int, amount: int) -> None:
    """Send a Telegram Stars invoice to the user (bot chat flow)."""
    tx, media, stars = await _build_star_invoice(user_id, amount)

    caption = (
        "🧾 <b>فاکتور استارز</b>\n"
        f"💡 شماره فاکتور: <code>{tx.invoice_no}</code>\n"
        f"💵 مبلغ: <code>{amount:,}</code> تومان ⭐ <code>{stars}</code> ستاره\n"
        "⏳ اعتبار: 30 دقیقه\n"
    )

    await Kenzo.send_message(user_id, message="⏳", parse_mode="html", buttons=await bhome_buttons(user_id, "fa"))
    message = await Kenzo.send_message(user_id, message=caption, file=media, parse_mode="html")
    await StarsTransactionCRUD().update(tx.id, message_id=message.id)


async def create_star_invoice_link(user_id: int, amount: int) -> tuple[StarsTransaction, str, int]:
    """Create a Stars invoice link usable with Telegram.WebApp.openInvoice."""
    tx, media, stars = await _build_star_invoice(user_id, amount)
    exported = await Kenzo(functions.payments.ExportInvoiceRequest(invoice_media=media))
    url = getattr(exported, "url", None) or ""
    if not url:
        raise ValueError("لینک فاکتور استارز ساخته نشد")
    return tx, url, stars


logger = get_logger(__name__)

_PRECHECKOUT_EXPIRED = "این فاکتور منقضی شده"


async def precheckout(event: types.UpdateBotPrecheckoutQuery):
    logger.info("Handler [precheckout]")
    payload = event.payload.decode("utf-8")
    ok = False
    if payload.startswith("stars:"):
        try:
            tx_id = int(payload.split(":", 1)[1])
        except ValueError:
            tx_id = None
        if tx_id is not None:
            tx = await StarsTransactionCRUD().get(tx_id)
            ok = stars_precheckout_ok(tx, now=int(time.time()))
    await Kenzo(
        functions.messages.SetBotPrecheckoutResultsRequest(
            query_id=event.query_id, success=ok, error=None if ok else _PRECHECKOUT_EXPIRED
        )
    )
    raise events.StopPropagation


async def payment_receiveddd(event):
    logger.info("Handler [payment_receiveddd]")
    payment = event.message.action

    try:
        payload = payment.payload.decode("utf-8")
    except Exception:
        # Telegram already charged the user; leave a trace for manual follow-up.
        logger.exception("Paid Stars invoice with an unreadable payload: user=%s", event.sender_id)
        return

    if not payload.startswith("stars:"):
        return

    try:
        tx_id = int(payload.split(":", 1)[1])
    except Exception:
        logger.exception("Paid Stars invoice with a malformed payload: user=%s payload=%s", event.sender_id, payload)
        return

    tx = await StarsTransactionCRUD().get(tx_id)
    if not tx:
        logger.warning(f"Stars payment transaction not found: tx_id={tx_id}, payload={payload}")
        raise events.StopPropagation

    user_id = tx.user_id
    toman = tx.amount

    try:
        settings = await SettingsManager().get_settings()
        bonus = await calculate_payment_bonus(
            amount=toman,
            bonus_enabled=settings.stars_bonus_enabled,
            bonus_percent=settings.stars_bonus_percent,
        )
        total_amount = toman + bonus

        approved = await StarsTransactionCRUD().approve_and_credit(tx_id, total_amount, int(time.time()))
        if not approved:
            logger.warning("Stars payment already processed or invalid: tx_id=%s", tx_id)
            raise events.StopPropagation
        _, new_amount = approved

        message_text = f"#فاکتور_استارز\n✅ پرداخت موفق! {int(toman):,} تومان به موجودی شما اضافه شد."
        if bonus > 0:
            message_text += f"\n🎁 بونوس: +{int(bonus):,} تومان ({settings.stars_bonus_percent}%)"
            message_text += f"\n💰 مجموع: {int(total_amount):,} تومان"
        message_text += f"\nشماره فاکتور: `{tx.invoice_no}`"

        await Kenzo.send_message(
            user_id,
            message_text,
            buttons=[[Button.inline(text=f"موجودی: {int(new_amount):,} تومان", data=b"no_action")]],
        )
    except Exception as e:
        logger.error(f"Payment handling error for tx_id={tx_id}: {e}", exc_info=True)
        await enqueue(message=f"Payment handling error: {e}", log_type=LogType.SYSTEM_ERROR)
        raise events.StopPropagation from None

    stars = payment.total_amount

    await enqueue(
        message=f"#پرداخت_استارز\nکاربر {user_id} به میزان {int(toman):,} تومان ({stars:.0f} ستاره) پرداخت کرد.\nفاکتور `{tx.invoice_no}`",
        log_type=LogType.STARS,
    )

    raise events.StopPropagation


def setup(ctx: PluginContext) -> None:
    ctx.add_event_handler(precheckout, events.Raw(types.UpdateBotPrecheckoutQuery))
    ctx.add_event_handler(
        payment_receiveddd,
        events.Raw(
            types.UpdateNewMessage,
            func=lambda u: (
                isinstance(getattr(u, "message", None), types.MessageService)
                and isinstance(getattr(u.message, "action", None), types.MessageActionPaymentSentMe)
            ),
        ),
    )
