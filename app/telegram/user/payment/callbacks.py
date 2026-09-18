import time

from telethon import Button, events, functions, types

from app import Kenzo
from app.db.crud.settings import SettingsManager
from app.db.crud.stars_transactions import StarsTransactionCRUD
from app.logger import LogType, get_logger
from app.services.billing.payment_bonus import calculate_payment_bonus
from app.services.send_queue import enqueue

logger = get_logger(__name__)


async def precheckout(event: types.UpdateBotPrecheckoutQuery):
    logger.info("Handler [precheckout]")
    payload = event.payload.decode("utf-8")
    if payload.startswith("stars:"):
        await Kenzo(
            functions.messages.SetBotPrecheckoutResultsRequest(query_id=event.query_id, success=True, error=None)
        )
    else:
        await Kenzo(
            functions.messages.SetBotPrecheckoutResultsRequest(
                query_id=event.query_id, success=False, error="این فاکتور منفضی شده"
            )
        )
    raise events.StopPropagation


async def payment_receiveddd(event):
    logger.info("Handler [payment_receiveddd]")
    payment = event.message.action

    try:
        payload = payment.payload.decode("utf-8")
    except Exception:
        return

    if not payload.startswith("stars:"):
        return

    try:
        tx_id = int(payload.split(":", 1)[1])
    except Exception:
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


def register(client):
    client.add_event_handler(precheckout, events.Raw(types.UpdateBotPrecheckoutQuery))
    client.add_event_handler(
        payment_receiveddd,
        events.Raw(
            types.UpdateNewMessage,
            func=lambda u: (
                isinstance(getattr(u, "message", None), types.MessageService)
                and isinstance(getattr(u.message, "action", None), types.MessageActionPaymentSentMe)
            ),
        ),
    )
