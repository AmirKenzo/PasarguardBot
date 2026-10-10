"""Top-up through any Iranian direct gateway inside the bot: amount, payment link and payment check."""

from __future__ import annotations

import contextlib

from telethon import Button, events
from telethon.tl.custom import Message

from app.db.crud.ir_gateway_payments import OPEN_STATUSES, IrGatewayPaymentCRUD
from app.db.crud.settings import SettingsManager
from app.db.models.ir_gateway_payment import IrGatewayPayment
from app.logger import get_logger
from app.services.billing.direct_pay_flow import (
    clamp_deposit_amount,
    get_direct_pay_prefilled_amount,
    is_direct_pay_active,
)
from app.services.billing.direct_pay_store import get_pending_for_user, link_crypto_order
from app.services.payments.ir_gateways import config
from app.services.payments.ir_gateways.providers import GATEWAYS, GatewayError
from app.services.payments.ir_gateways.service import (
    create_deposit,
    gateway_title,
    payment_url,
    status_label,
    verify_payment,
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

_GATEWAY_DATA_KEY = "ir_gateway_key"


def payment_text(payment: IrGatewayPayment) -> str:
    title = gateway_title(payment.gateway)
    lines = [
        f"<b>✅ لینک پرداخت {title} ساخته شد.</b>",
        "- -",
        f"🧾 شناسه سفارش: <code>{payment.order_id}</code>",
        f"<b>💵 مبلغ شارژ:</b> <code>{int(payment.amount):,}</code> <b>تومان</b>",
        f"<b>📌 وضعیت:</b> {status_label(payment.status)}",
    ]
    if payment.sandbox:
        lines += ["", "🧪 <b>حالت تست:</b> پرداخت واقعی انجام نمی‌شود و فقط برای ادمین نمایش داده می‌شود."]
    if payment.status in OPEN_STATUSES:
        lines += [
            "",
            f"روی «پرداخت» بزنید و پرداخت را در درگاه {title} کامل کنید.",
            "پس از پرداخت، موجودی شما خودکار شارژ می‌شود؛ اگر نشد «بررسی پرداخت» را بزنید.",
            "⏳ این لینک تا ۳۰ دقیقه معتبر است.",
        ]
    elif payment.status == "completed":
        lines.append(f"🔖 کد پیگیری: <code>{payment.ref_id or '—'}</code>")
    return "\n".join(lines)


def payment_buttons(payment: IrGatewayPayment) -> list:
    if payment.status not in OPEN_STATUSES:
        return [[Button.inline(f"📌 {status_label(payment.status)}", data="no_action")]]
    rows: list[list] = []
    url = payment_url(payment)
    if url:
        rows.append([Button.url("💳 پرداخت", url)])
    rows.append([Button.inline("🔍 بررسی پرداخت", data=f"{states.CALLBACK_IR_GATEWAY_CHECK_PREFIX}{payment.id}")])
    return rows


async def _create_and_send(event, key: str, user_id: int, amount: int) -> None:
    try:
        payment = await create_deposit(key, user_id, amount, source="bot")
    except GatewayError as e:
        await event.respond(f"❌ {e.message}", buttons=await balance_flow_cancel_rows())
        return
    await event.respond("⏳", buttons=await bhome_buttons(user_id, "fa"))
    message = await event.respond(payment_text(payment), buttons=payment_buttons(payment), parse_mode="html")
    await IrGatewayPaymentCRUD().update(payment.id, message_id=message.id)
    if await is_direct_pay_active(user_id) or await get_pending_for_user(user_id):
        await link_crypto_order(int(user_id), int(payment.id))
        await clear_user(user_id)
    await set_step(user_id, states.STEP_HOME)


@bot_is_offline
@debounce_callback()
async def ir_gateway_pay_callback(event: events.CallbackQuery.Event):
    if not await _require_balance_payment_step(event):
        return
    key = event.data.decode("utf-8").removeprefix(states.CALLBACK_IR_GATEWAY_PREFIX)
    settings = await SettingsManager().get_settings()
    if key not in GATEWAYS or not config.is_available_for(settings, key, event.sender_id):
        await event.answer(texts.PAYMENT_DISABLED_ALERT, alert=True)
        raise events.StopPropagation
    provider = GATEWAYS[key]
    min_amount, max_amount = config.deposit_limits(settings, key)
    if await is_direct_pay_active(event.sender_id):
        amount = await get_direct_pay_prefilled_amount(event.sender_id)
        if amount is None:
            await event.answer(texts.ENTER_AMOUNT_FIRST_ALERT, alert=True)
            raise events.StopPropagation
        amount = clamp_deposit_amount(amount, min_amount, max_amount)
        await set_data(event.sender_id, "mablagh", amount)
        await _create_and_send(event, key, event.sender_id, amount)
        raise events.StopPropagation
    await event.edit(
        f"{provider.emoji} مبلغ شارژ با {provider.title} را به تومان وارد کنید.\n\n"
        f"حداقل: {min_amount:,} تومان\nحداکثر: {max_amount:,} تومان",
        buttons=await balance_flow_cancel_rows(),
    )
    await remember_balance_flow_message(event.sender_id, event.message_id)
    await set_data(event.sender_id, _GATEWAY_DATA_KEY, key)
    await set_step(event.sender_id, states.STEP_IR_GATEWAY_2)
    raise events.StopPropagation


async def ir_gateway_amount_filter(event) -> bool:
    if event.is_channel or not event.is_private:
        return False
    if await get_step(event.sender_id) != states.STEP_IR_GATEWAY_2:
        return False
    msg = event.message.message
    return bool(msg) and not _is_nav_command(msg)


@bot_is_offline
async def ir_gateway_amount_handler(event: Message):
    msg = (event.message.message or "").replace(",", "").strip()
    if not msg.isdigit():
        await event.respond("❌ لطفاً فقط عدد وارد کنید. مثال: 100000", buttons=await balance_flow_cancel_rows())
        raise events.StopPropagation
    key = str(await get_data(event.sender_id, _GATEWAY_DATA_KEY) or "")
    if key not in GATEWAYS:
        await event.respond(texts.PAYMENT_DISABLED_ALERT, buttons=await bhome_buttons(event.sender_id, "fa"))
        await set_step(event.sender_id, states.STEP_HOME)
        raise events.StopPropagation
    await _create_and_send(event, key, event.sender_id, int(msg))
    raise events.StopPropagation


@bot_is_offline
@debounce_callback()
async def ir_gateway_check_callback(event: events.CallbackQuery.Event):
    try:
        local_id = int(event.data.decode("utf-8").removeprefix(states.CALLBACK_IR_GATEWAY_CHECK_PREFIX))
    except ValueError:
        raise events.StopPropagation from None
    payment = await IrGatewayPaymentCRUD().get_for_user(local_id, event.sender_id)
    if not payment:
        await event.answer("پرداخت پیدا نشد.", alert=True)
        raise events.StopPropagation
    try:
        payment = await verify_payment(payment)
    except GatewayError as e:
        await event.answer(e.message, alert=True)
        raise events.StopPropagation from None
    if payment.status == "completed":
        await event.answer("✅ پرداخت تأیید شد و موجودی شارژ شد.", alert=True)
    elif payment.status in OPEN_STATUSES:
        await event.answer("⏳ هنوز پرداختی ثبت نشده است. بعد از پرداخت دوباره بررسی کنید.", alert=True)
    else:
        await event.answer(f"📌 وضعیت پرداخت: {status_label(payment.status)}", alert=True)
    with contextlib.suppress(Exception):
        await event.edit(payment_text(payment), buttons=payment_buttons(payment), parse_mode="html")
    raise events.StopPropagation


def register(client):
    client.add_event_handler(
        ir_gateway_pay_callback,
        events.CallbackQuery(pattern=f"^{states.CALLBACK_IR_GATEWAY_PREFIX}".encode()),
    )
    client.add_event_handler(
        ir_gateway_check_callback,
        events.CallbackQuery(pattern=f"^{states.CALLBACK_IR_GATEWAY_CHECK_PREFIX}".encode()),
    )
    client.add_event_handler(ir_gateway_amount_handler, events.NewMessage(incoming=True, func=ir_gateway_amount_filter))
