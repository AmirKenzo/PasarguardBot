"""TonPays top-up flow inside the bot: amount, invoice, payment check, card change and receipt upload."""

from __future__ import annotations

import contextlib
from io import BytesIO

from telethon import Button, events
from telethon.tl.custom import Message

from app.db.crud.settings import SettingsManager
from app.db.crud.tonpays_invoices import OPEN_STATUSES, TonPaysInvoiceCRUD
from app.db.models.tonpays_invoice import TonPaysInvoice
from app.logger import get_logger
from app.services.billing.direct_pay_flow import (
    clamp_deposit_amount,
    get_direct_pay_prefilled_amount,
    is_direct_pay_active,
)
from app.services.billing.direct_pay_store import get_pending_for_user, link_crypto_order
from app.services.payments.tonpays import (
    MODE_CUSTOM,
    TonPaysError,
    change_card,
    create_deposit,
    deposit_limits,
    is_ready,
    refresh_invoice,
    status_label,
    submit_receipt,
)
from app.telegram.keyboards.balance import balance_flow_cancel_rows
from app.telegram.keyboards.home import bhome_buttons
from app.telegram.shared.utils.maintenance import bot_is_offline
from app.telegram.shared.utils.rate_limit import debounce_callback
from app.telegram.state import clear_user, get_data, get_step, set_data, set_step
from app.telegram.user.balance import states, texts
from app.telegram.user.balance.messages import (
    _is_nav_command,
    _require_balance_payment_step,
    remember_balance_flow_message,
)

logger = get_logger(__name__)

_RECEIPT_DATA_KEY = "tonpays_receipt_invoice"


def invoice_text(invoice: TonPaysInvoice) -> str:
    final_amount = int(invoice.final_amount or invoice.amount)
    lines = [
        "<b>✅ فاکتور پرداخت TonPays ایجاد شد.</b>",
        "- -",
        f"➿ شماره فاکتور: <code>{invoice.invoice_id}</code>",
        f"<b>💵 مبلغ شارژ:</b> <code>{int(invoice.amount):,}</code> <b>تومان</b>",
        f"<b>💰 مبلغ قابل پرداخت:</b> <code>{final_amount:,}</code> <b>تومان</b>",
        f"<b>📌 وضعیت:</b> {status_label(invoice.status)}",
        "",
        f"⚠️ <b>دقیقاً مبلغ {final_amount:,} تومان را پرداخت کنید؛ با مبلغ دیگر پرداخت تأیید نمی‌شود.</b>",
    ]
    if invoice.mode == MODE_CUSTOM:
        lines += [
            "",
            "💳 <b>شماره کارت:</b>",
            f"<code>{invoice.card_number or '—'}</code>",
            f"👤 <b>به نام:</b> {invoice.card_name or '—'}",
            "",
            "بعد از واریز، روی «ارسال فیش» بزنید و عکس فیش را بفرستید.",
        ]
    else:
        lines += ["", "روی «پرداخت» بزنید و پرداخت را در ربات TonPays کامل کنید."]
    lines.append("پس از تأیید، موجودی شما خودکار شارژ می‌شود.")
    return "\n".join(lines)


def invoice_buttons(invoice: TonPaysInvoice) -> list:
    if invoice.status not in OPEN_STATUSES:
        return [[Button.inline(f"📌 {status_label(invoice.status)}", data="no_action")]]
    rows: list[list] = []
    if invoice.mode == MODE_CUSTOM:
        if not invoice.receipt_sent:
            rows.append([Button.inline("🧾 ارسال فیش", data=f"{states.CALLBACK_TONPAYS_RECEIPT_PREFIX}{invoice.id}")])
        rows.append([Button.inline("🔄 تعویض کارت", data=f"{states.CALLBACK_TONPAYS_CARD_PREFIX}{invoice.id}")])
    elif invoice.invoice_url:
        rows.append([Button.url("💳 پرداخت", invoice.invoice_url)])
    rows.append([Button.inline("🔍 بررسی پرداخت", data=f"{states.CALLBACK_TONPAYS_CHECK_PREFIX}{invoice.id}")])
    return rows


async def _create_and_send(event, user_id: int, amount: int) -> None:
    try:
        invoice = await create_deposit(user_id, amount, source="bot")
    except TonPaysError as e:
        await event.respond(f"❌ {e.message}", buttons=await balance_flow_cancel_rows())
        return
    await event.respond("⏳", buttons=await bhome_buttons(user_id, "fa"))
    message = await event.respond(invoice_text(invoice), buttons=invoice_buttons(invoice), parse_mode="html")
    await TonPaysInvoiceCRUD().update(invoice.id, message_id=message.id)
    if await is_direct_pay_active(user_id) or await get_pending_for_user(user_id):
        await link_crypto_order(int(user_id), int(invoice.id))
        await clear_user(user_id)
    await set_step(user_id, states.STEP_HOME)


async def _owned_invoice(event, prefix: str) -> TonPaysInvoice | None:
    try:
        local_id = int(event.data.decode("utf-8").removeprefix(prefix))
    except ValueError:
        return None
    invoice = await TonPaysInvoiceCRUD().get_for_user(local_id, event.sender_id)
    if not invoice:
        await event.answer("فاکتور پیدا نشد.", alert=True)
    return invoice


async def _edit_invoice_message(event, invoice: TonPaysInvoice) -> None:
    with contextlib.suppress(Exception):
        await event.edit(invoice_text(invoice), buttons=invoice_buttons(invoice), parse_mode="html")


@bot_is_offline
@debounce_callback()
async def tonpays_payment_callback(event: events.CallbackQuery.Event):
    if not await _require_balance_payment_step(event):
        return
    settings = await SettingsManager().get_settings()
    if not is_ready(settings):
        await event.answer(texts.PAYMENT_DISABLED_ALERT, alert=True)
        raise events.StopPropagation
    min_amount, max_amount = deposit_limits(settings)
    if await is_direct_pay_active(event.sender_id):
        amount = await get_direct_pay_prefilled_amount(event.sender_id)
        if amount is None:
            await event.answer(texts.ENTER_AMOUNT_FIRST_ALERT, alert=True)
            raise events.StopPropagation
        amount = clamp_deposit_amount(amount, min_amount, max_amount)
        await set_data(event.sender_id, "mablagh", amount)
        await _create_and_send(event, event.sender_id, amount)
        raise events.StopPropagation
    await event.edit(
        f"💎 مبلغ شارژ را به تومان وارد کنید.\n\nحداقل: {min_amount:,} تومان\nحداکثر: {max_amount:,} تومان",
        buttons=await balance_flow_cancel_rows(),
    )
    await remember_balance_flow_message(event.sender_id, event.message_id)
    await set_step(event.sender_id, states.STEP_TONPAYS_2)
    raise events.StopPropagation


async def tonpays_amount_filter(event) -> bool:
    if event.is_channel or not event.is_private:
        return False
    if await get_step(event.sender_id) != states.STEP_TONPAYS_2:
        return False
    msg = event.message.message
    return bool(msg) and not _is_nav_command(msg)


@bot_is_offline
async def tonpays_amount_handler(event: Message):
    msg = (event.message.message or "").replace(",", "").strip()
    if not msg.isdigit():
        await event.respond("❌ لطفاً فقط عدد وارد کنید. مثال: 100000", buttons=await balance_flow_cancel_rows())
        raise events.StopPropagation
    await _create_and_send(event, event.sender_id, int(msg))
    raise events.StopPropagation


@bot_is_offline
@debounce_callback()
async def tonpays_check_callback(event: events.CallbackQuery.Event):
    invoice = await _owned_invoice(event, states.CALLBACK_TONPAYS_CHECK_PREFIX)
    if not invoice:
        raise events.StopPropagation
    invoice = await refresh_invoice(invoice)
    if invoice.status == "completed":
        await event.answer("✅ پرداخت تأیید شد و موجودی شارژ شد.", alert=True)
    else:
        await event.answer(f"📌 وضعیت فاکتور: {status_label(invoice.status)}", alert=True)
    await _edit_invoice_message(event, invoice)
    raise events.StopPropagation


@bot_is_offline
@debounce_callback()
async def tonpays_card_callback(event: events.CallbackQuery.Event):
    invoice = await _owned_invoice(event, states.CALLBACK_TONPAYS_CARD_PREFIX)
    if not invoice:
        raise events.StopPropagation
    try:
        data = await change_card(invoice)
    except TonPaysError as e:
        await event.answer(e.message, alert=True)
        raise events.StopPropagation from None
    if data.get("change_card_exhausted"):
        await event.answer("کارت دیگری برای تعویض موجود نیست.", alert=True)
    else:
        await event.answer("✅ کارت تعویض شد.")
    invoice = await TonPaysInvoiceCRUD().get(invoice.id) or invoice
    await _edit_invoice_message(event, invoice)
    raise events.StopPropagation


@bot_is_offline
@debounce_callback()
async def tonpays_receipt_callback(event: events.CallbackQuery.Event):
    invoice = await _owned_invoice(event, states.CALLBACK_TONPAYS_RECEIPT_PREFIX)
    if not invoice:
        raise events.StopPropagation
    if invoice.status not in OPEN_STATUSES:
        await event.answer(f"📌 وضعیت فاکتور: {status_label(invoice.status)}", alert=True)
        raise events.StopPropagation
    await set_data(event.sender_id, _RECEIPT_DATA_KEY, invoice.id)
    await set_step(event.sender_id, states.STEP_TONPAYS_RECEIPT)
    await event.respond("🧾 عکس فیش واریزی را ارسال کنید:", buttons=await balance_flow_cancel_rows())
    raise events.StopPropagation


async def tonpays_receipt_filter(event) -> bool:
    if event.is_channel or not event.is_private:
        return False
    if await get_step(event.sender_id) != states.STEP_TONPAYS_RECEIPT:
        return False
    msg = event.message.message
    return not (msg and _is_nav_command(msg))


@bot_is_offline
async def tonpays_receipt_handler(event: Message):
    if not event.message.photo:
        await event.respond("❌ لطفاً عکس فیش را ارسال کنید.", buttons=await balance_flow_cancel_rows())
        raise events.StopPropagation
    local_id = await get_data(event.sender_id, _RECEIPT_DATA_KEY)
    invoice = await TonPaysInvoiceCRUD().get_for_user(int(local_id or 0), event.sender_id)
    if not invoice:
        await event.respond("❌ فاکتور پیدا نشد.")
        await set_step(event.sender_id, states.STEP_HOME)
        raise events.StopPropagation
    buffer = BytesIO()
    await event.message.download_media(file=buffer)
    try:
        invoice = await submit_receipt(invoice, buffer.getvalue(), f"receipt_{invoice.order_id}.jpg", "image/jpeg")
    except TonPaysError as e:
        await event.respond(f"❌ {e.message}", buttons=await balance_flow_cancel_rows())
        raise events.StopPropagation from None
    await clear_user(event.sender_id)
    await set_step(event.sender_id, states.STEP_HOME)
    await event.respond(
        "✅ فیش ارسال شد و در انتظار تأیید است. پس از تأیید، موجودی شما خودکار شارژ می‌شود.",
        buttons=await bhome_buttons(event.sender_id, "fa"),
    )
    raise events.StopPropagation


def register(client):
    client.add_event_handler(tonpays_payment_callback, events.CallbackQuery(data=states.CALLBACK_TONPAYS))
    client.add_event_handler(
        tonpays_check_callback,
        events.CallbackQuery(pattern=f"^{states.CALLBACK_TONPAYS_CHECK_PREFIX}".encode()),
    )
    client.add_event_handler(
        tonpays_card_callback,
        events.CallbackQuery(pattern=f"^{states.CALLBACK_TONPAYS_CARD_PREFIX}".encode()),
    )
    client.add_event_handler(
        tonpays_receipt_callback,
        events.CallbackQuery(pattern=f"^{states.CALLBACK_TONPAYS_RECEIPT_PREFIX}".encode()),
    )
    client.add_event_handler(tonpays_amount_handler, events.NewMessage(incoming=True, func=tonpays_amount_filter))
    client.add_event_handler(tonpays_receipt_handler, events.NewMessage(incoming=True, func=tonpays_receipt_filter))
