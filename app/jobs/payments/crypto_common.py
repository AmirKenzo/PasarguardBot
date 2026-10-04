"""Shared confirm / expire helpers for the USDT-TON, USDT-BEP20 and POL processors."""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime
from decimal import Decimal

from telethon import Button

from app import Kenzo
from app.db.crud.cryptopayments import CryptoPaymentsCRUD
from app.logger import LogType, get_logger
from app.services.billing.direct_pay_fulfillment import (
    cancel_after_crypto_expire,
    try_fulfill_after_crypto_credit,
)
from app.services.billing.payment_bonus import calculate_payment_bonus
from app.telegram.shared.utils.logging import send_log_message

logger = get_logger(__name__)

INVOICE_TTL_SECONDS = 30 * 60


def amount_matches(payment_amount, received: Decimal | float) -> bool:
    left = Decimal(str(payment_amount)).quantize(Decimal("0.000001"))
    right = Decimal(str(received)).quantize(Decimal("0.000001"))
    return abs(left - right) <= Decimal("0.000001")


def is_expired(payment) -> bool:
    return int(datetime.now(UTC).timestamp()) - int(payment.createtime or 0) > INVOICE_TTL_SECONDS


def _format_tx_time(timestamp) -> str:
    try:
        ts = int(timestamp or 0)
        if ts > 10_000_000_000:
            ts //= 1000
        return datetime.fromtimestamp(ts, tz=UTC).strftime("%Y-%m-%d %H:%M:%S UTC") if ts else "N/A"
    except TypeError, ValueError, OSError:
        return "N/A"


async def confirm_payment(payment, settings, tx_details: dict, *, unit: str, price_line: str) -> None:
    """Credit the invoice once, then notify the user (unless direct-pay took over) and the log channel."""
    bonus = await calculate_payment_bonus(
        amount=int(payment.amount_irt),
        bonus_enabled=settings.crypto_bonus_enabled,
        bonus_percent=settings.crypto_bonus_percent,
    )
    total_amount = int(payment.amount_irt) + bonus
    paytime = int(datetime.now(UTC).timestamp())
    approved = await CryptoPaymentsCRUD().approve_and_credit(payment.order_id, total_amount, paytime)
    if not approved:
        logger.warning("%s payment already processed or invalid: order_id=%s", payment.arz, payment.order_id)
        return
    payment, new_amount = approved

    network = (payment.arz or "").upper()
    balance_btn = [[Button.inline(text=f"💳 موجودی: {int(new_amount):,} تومان", data="no_action")]]
    bonus_lines: list[str] = []
    if bonus > 0:
        bonus_lines = [
            f"🎁 <b>بونوس:</b> +<code>{int(bonus):,}</code> تومان ({settings.crypto_bonus_percent}%)",
            f"💰 <b>مجموع:</b> <code>{int(total_amount):,}</code> تومان",
        ]
    try:
        if not await try_fulfill_after_crypto_credit(int(payment.order_id)):
            user_msg = "\n".join(
                [
                    "🎉 <b>پرداخت شما با موفقیت انجام شد!</b>",
                    "",
                    f"📋 <b>شماره فاکتور:</b> <code>{payment.order_id}</code>",
                    f"💵 <b>مبلغ:</b> <code>{int(payment.amount_irt):,}</code> تومان",
                    *bonus_lines,
                    f"💎 <b>مقدار {unit}:</b> <code>{payment.amount}</code> {unit}",
                    f"🧬 <b>شبکه:</b> <code>{network}</code>",
                    price_line,
                    "",
                    f"💳 <b>موجودی جدید:</b> <code>{int(new_amount):,}</code> تومان",
                    "",
                    f"<code>#{payment.arz}_{payment.order_id}</code>",
                ]
            )
            await Kenzo.send_message(payment.user_id, user_msg, parse_mode="html", buttons=balance_btn)

        explorer = tx_details.get("explorer_html") or ""
        admin_log = "\n".join(
            [
                "#فاکتور_ارزی",
                "<b>✅ فاکتور ارزی کاربر با موفقیت پرداخت شد</b>",
                "",
                f"<b>👤 شناسه کاربری:</b> <code>{payment.user_id}</code> | "
                f"<a href='tg://user?id={payment.user_id}'>پروفایل کاربر</a>",
                f"<b>📋 شماره فاکتور:</b> <code>{payment.order_id}</code>",
                f"<b>💵 مبلغ فاکتور:</b> <code>{int(payment.amount_irt):,}</code> تومان",
                *bonus_lines,
                f"<b>💎 مقدار {unit}:</b> <code>{payment.amount}</code> {unit}",
                f"<b>🧬 شبکه:</b> <code>{network}</code>",
                price_line,
                f"<b>💳 موجودی جدید کاربر:</b> <code>{int(new_amount):,}</code> تومان",
                "",
                "<b>🔗 جزئیات تراکنش بلاکچین:</b>",
                f"<b>📝 هش تراکنش:</b> <code>{tx_details.get('hash', 'N/A')}</code>",
                f"<b>👤 از آدرس:</b> <code>{tx_details.get('from', 'N/A')}</code>",
                f"<b>👥 به آدرس:</b> <code>{tx_details.get('to', 'N/A')}</code>",
                f"<b>⏰ زمان تراکنش:</b> <code>{_format_tx_time(tx_details.get('timestamp'))}</code>",
                f"<b>📦 بلاک/LT:</b> <code>{tx_details.get('block', 'N/A')}</code>",
                f"<b>✅ وضعیت:</b> {'تایید شده' if tx_details.get('confirmed', True) else 'در انتظار تایید'}",
                *([explorer] if explorer else []),
                "",
                f"<code>#{payment.arz}_{payment.order_id}</code>",
            ]
        )
        await send_log_message(LogType.CRYPTO, message=admin_log, parse_mode="html", buttons=balance_btn)
    except Exception as e:
        logger.error("Post-credit notification failed for order_id=%s: %s", payment.order_id, e)


async def expire_payment(payment, *, unit: str, price_line: str) -> None:
    await CryptoPaymentsCRUD().expire_payment(payment.order_id)
    await cancel_after_crypto_expire(int(payment.order_id))
    network = (payment.arz or "").upper()
    try:
        if getattr(payment, "msg_id", None):
            with contextlib.suppress(Exception):
                await Kenzo.delete_messages(payment.user_id, payment.msg_id)
        await Kenzo.send_message(
            payment.user_id,
            (
                f"<b>#اطلاع_رسانی</b>\n\n"
                f"<b>📅 فاکتور شماره [ {payment.order_id} ] به دلیل گذشتن زمان منقضی شد.</b>\n"
                f"<b>💵 مبلغ فاکتور:</b> <code>{int(payment.amount_irt):,}</code> <b>تومان</b>\n"
                f"<b>💰 مقدار {unit}:</b> <code>{payment.amount}</code> {unit}\n"
                f"<b>🧬 شبکه:</b> <code>{network}</code>\n"
                f"{price_line}\n"
                f"<b>#notification_{payment.order_id}</b>"
            ),
            parse_mode="html",
            buttons=[[Button.inline(text="🚫 منقضی شد", data="no_action")]],
        )
        await send_log_message(
            LogType.CRYPTO,
            message=(
                "#فاکتور_منقضی\n"
                f"👤 شناسه کاربر: <code>{payment.user_id}</code> | "
                f"<a href='tg://user?id={payment.user_id}'>پروفایل کاربر</a>\n"
                f"💡 شماره فاکتور: <code>{payment.order_id}</code>\n"
                f"💵 مبلغ فاکتور: <code>{int(payment.amount_irt):,}</code> تومان\n"
                f"💰 مقدار {unit}: <code>{payment.amount}</code>\n"
                f"🧬 شبکه: {network}\n"
                f"#{network.lower().replace('-', '_')}_{payment.order_id}"
            ),
            parse_mode="html",
        )
    except Exception as e:
        logger.error("Expire notification failed for order_id=%s: %s", payment.order_id, e)
