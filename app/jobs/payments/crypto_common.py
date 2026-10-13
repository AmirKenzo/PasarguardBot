"""Shared match / confirm / expire flow for the on-chain crypto processors.

Each chain module only fetches and parses its explorer data and supplies small hooks
(candidate filter, amount check, notice texts); crediting, tx-hash dedupe, notifications
and expiry of overdue invoices live here.
"""

from __future__ import annotations

import contextlib
import logging
import time
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from telethon import Button, errors

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

# User-facing invoice lifetime.
INVOICE_TTL_SECONDS = 30 * 60
INVOICE_EXPIRY_GRACE_SECONDS = 10 * 60
TX_TIME_TOLERANCE_SECONDS = 2 * 60
_MS_THRESHOLD = 10_000_000_000

TextRenderer = Callable[[Any, int, int, Any], str]


def amount_matches(payment_amount, received: Decimal | float) -> bool:
    left = Decimal(str(payment_amount)).quantize(Decimal("0.000001"))
    right = Decimal(str(received)).quantize(Decimal("0.000001"))
    return abs(left - right) <= Decimal("0.000001")


def to_unix_seconds(timestamp: Any) -> int:
    try:
        ts = int(timestamp or 0)
    except TypeError, ValueError:
        return 0
    if ts > _MS_THRESHOLD:
        ts //= 1000
    return max(ts, 0)


def is_past_expiry_grace(payment, now: int | None = None) -> bool:
    current = int(datetime.now(UTC).timestamp()) if now is None else now
    return current - int(payment.createtime or 0) > INVOICE_TTL_SECONDS + INVOICE_EXPIRY_GRACE_SECONDS


def tx_time_in_window(payment, tx_timestamp: Any, *, allow_unknown: bool = False) -> bool:
    ts = to_unix_seconds(tx_timestamp)
    created = int(payment.createtime or 0)
    if ts <= 0:
        return allow_unknown and int(time.time()) - created <= INVOICE_TTL_SECONDS
    return created <= ts <= created + INVOICE_TTL_SECONDS + TX_TIME_TOLERANCE_SECONDS


async def expire_unmatched(
    payments: Iterable[Any],
    matched_order_ids: set[int],
    expire: Callable[[Any], Awaitable[None]],
) -> None:
    now = int(datetime.now(UTC).timestamp())
    for payment in payments:
        if int(payment.order_id) in matched_order_ids:
            continue
        if is_past_expiry_grace(payment, now):
            await expire(payment)


async def match_transfers[T](
    payments: Iterable[Any],
    candidates: Callable[[Any], Iterable[T]],
    consumed: set[str],
    *,
    tx_id: Callable[[T], str | None],
    accepts: Callable[[Any, T], Awaitable[bool]],
    confirm: Callable[[Any, T, str], Awaitable[None]],
    name: str,
    error_message: str,
    log: logging.Logger,
    retry_after_error: bool = False,
) -> set[int]:
    """Pair each pending invoice with at most one unused transfer and credit it; return matched order ids.

    ``candidates(payment)`` yields the chain's transfers already filtered to the invoice window.
    A transfer id is reserved in ``consumed`` before crediting, so one transfer never pays two invoices.
    With ``retry_after_error`` a failed confirm moves on to the invoice's next candidate.
    """
    matched: set[int] = set()
    for payment in payments:
        for candidate in candidates(payment):
            txid = tx_id(candidate)
            if txid in consumed:
                continue
            if not await accepts(payment, candidate):
                continue
            if txid is None:
                log.warning("%s transfer for order_id=%s has no tx id; not crediting", name, payment.order_id)
                continue
            consumed.add(txid)
            matched.add(int(payment.order_id))
            try:
                await confirm(payment, candidate, txid)
            except Exception as e:
                log.error(error_message, payment.order_id, e)
                if retry_after_error:
                    continue
            break
    return matched


# ---------------------------------------------------------------------------
# Credit / expire core
# ---------------------------------------------------------------------------


async def _credit_and_notify(
    payment,
    settings,
    tx_hash: str,
    *,
    name: str,
    log: logging.Logger,
    user_text: TextRenderer,
    log_text: TextRenderer,
) -> None:
    """Credit the invoice once, then notify the user (unless direct-pay took over) and the log channel."""
    bonus = await calculate_payment_bonus(
        amount=int(payment.amount_irt),
        bonus_enabled=settings.crypto_bonus_enabled,
        bonus_percent=settings.crypto_bonus_percent,
    )
    total_amount = int(payment.amount_irt) + bonus
    paytime = int(datetime.now(UTC).timestamp())
    approved = await CryptoPaymentsCRUD().approve_and_credit(payment.order_id, total_amount, paytime, tx_hash=tx_hash)
    if not approved:
        log.warning("%s payment already processed or invalid: order_id=%s", name, payment.order_id)
        return
    payment, new_amount = approved

    balance_btn = [[Button.inline(text=f"💳 موجودی: {int(new_amount):,} تومان", data="no_action")]]
    try:
        if not await try_fulfill_after_crypto_credit(int(payment.order_id)):
            text = user_text(payment, bonus, total_amount, new_amount)
            await Kenzo.send_message(payment.user_id, text, parse_mode="html", buttons=balance_btn)
        text = log_text(payment, bonus, total_amount, new_amount)
        await send_log_message(LogType.CRYPTO, message=text, parse_mode="html", buttons=balance_btn)
    except Exception as e:
        log.error("Post-credit notification failed for order_id=%s: %s", payment.order_id, e)


async def _expire_and_notify(
    payment,
    *,
    user_text: Callable[[], str],
    log_text: Callable[[], str],
    on_failure: Callable[[Exception], None],
) -> None:
    if not await CryptoPaymentsCRUD().expire_payment(payment.order_id):
        return
    await cancel_after_crypto_expire(int(payment.order_id))
    try:
        if getattr(payment, "msg_id", None):
            with contextlib.suppress(Exception):
                await Kenzo.delete_messages(payment.user_id, payment.msg_id)
        await Kenzo.send_message(
            payment.user_id,
            user_text(),
            parse_mode="html",
            buttons=[[Button.inline(text="🚫 منقضی شد", data="no_action")]],
        )
        await send_log_message(LogType.CRYPTO, message=log_text(), parse_mode="html")
    except Exception as e:
        on_failure(e)


def _bonus_lines(bonus: int, total_amount: int, settings, *, bold_emoji: bool = False) -> list[str]:
    if bonus <= 0:
        return []
    if bold_emoji:
        return [
            f"<b>🎁 بونوس:</b> +<code>{int(bonus):,}</code> تومان ({settings.crypto_bonus_percent}%)",
            f"<b>💰 مجموع:</b> <code>{int(total_amount):,}</code> تومان",
        ]
    return [
        f"🎁 <b>بونوس:</b> +<code>{int(bonus):,}</code> تومان ({settings.crypto_bonus_percent}%)",
        f"💰 <b>مجموع:</b> <code>{int(total_amount):,}</code> تومان",
    ]


def _credit_user_text(payment, new_amount, *, bonus_lines: list[str], asset_lines: list[str]) -> str:
    return "\n".join(
        [
            "🎉 <b>پرداخت شما با موفقیت انجام شد!</b>",
            "",
            f"📋 <b>شماره فاکتور:</b> <code>{payment.order_id}</code>",
            f"💵 <b>مبلغ:</b> <code>{int(payment.amount_irt):,}</code> تومان",
            *bonus_lines,
            *asset_lines,
            "",
            f"💳 <b>موجودی جدید:</b> <code>{int(new_amount):,}</code> تومان",
            "",
            f"<code>#{payment.arz}_{payment.order_id}</code>",
        ]
    )


def _credit_log_text(
    payment,
    new_amount,
    tx_details: dict,
    *,
    bonus_lines: list[str],
    asset_lines: list[str],
    tx_time: str,
    block_label: str,
    explorer_lines: list[str],
) -> str:
    return "\n".join(
        [
            "#فاکتور_ارزی",
            "<b>✅ فاکتور ارزی کاربر با موفقیت پرداخت شد</b>",
            "",
            f"<b>👤 شناسه کاربری:</b> <code>{payment.user_id}</code> | "
            f"<a href='tg://user?id={payment.user_id}'>پروفایل کاربر</a>",
            f"<b>📋 شماره فاکتور:</b> <code>{payment.order_id}</code>",
            f"<b>💵 مبلغ فاکتور:</b> <code>{int(payment.amount_irt):,}</code> تومان",
            *bonus_lines,
            *asset_lines,
            f"<b>💳 موجودی جدید کاربر:</b> <code>{int(new_amount):,}</code> تومان",
            "",
            "<b>🔗 جزئیات تراکنش بلاکچین:</b>",
            f"<b>📝 هش تراکنش:</b> <code>{tx_details.get('hash', 'N/A')}</code>",
            f"<b>👤 از آدرس:</b> <code>{tx_details.get('from', 'N/A')}</code>",
            f"<b>👥 به آدرس:</b> <code>{tx_details.get('to', 'N/A')}</code>",
            f"<b>⏰ زمان تراکنش:</b> <code>{tx_time}</code>",
            f"<b>📦 {block_label}:</b> <code>{tx_details.get('block', 'N/A')}</code>",
            f"<b>✅ وضعیت:</b> {'تایید شده' if tx_details.get('confirmed', True) else 'در انتظار تایید'}",
            *explorer_lines,
            "",
            f"<code>#{payment.arz}_{payment.order_id}</code>",
        ]
    )


def _expire_user_text(payment, asset_lines: list[str]) -> str:
    return (
        f"<b>#اطلاع_رسانی</b>\n\n"
        f"<b>📅 فاکتور شماره [ {payment.order_id} ] به دلیل گذشتن زمان منقضی شد.</b>\n"
        f"<b>💵 مبلغ فاکتور:</b> <code>{int(payment.amount_irt):,}</code> <b>تومان</b>\n"
        + "".join(f"{line}\n" for line in asset_lines)
        + f"<b>#notification_{payment.order_id}</b>"
    )


def _expire_log_text(payment, asset_lines: list[str], tag: str) -> str:
    return (
        "#فاکتور_منقضی\n"
        f"👤 شناسه کاربر: <code>{payment.user_id}</code> | "
        f"<a href='tg://user?id={payment.user_id}'>پروفایل کاربر</a>\n"
        f"💡 شماره فاکتور: <code>{payment.order_id}</code>\n"
        f"💵 مبلغ فاکتور: <code>{int(payment.amount_irt):,}</code> تومان\n"
        + "".join(f"{line}\n" for line in asset_lines)
        + f"#{tag}_{payment.order_id}"
    )


# ---------------------------------------------------------------------------
# Network-labelled notices (POL, USDT-TON, USDT-BEP20)
# ---------------------------------------------------------------------------


def _format_tx_time(timestamp) -> str:
    try:
        ts = int(timestamp or 0)
        if ts > 10_000_000_000:
            ts //= 1000
        return datetime.fromtimestamp(ts, tz=UTC).strftime("%Y-%m-%d %H:%M:%S UTC") if ts else "N/A"
    except TypeError, ValueError, OSError:
        return "N/A"


async def confirm_payment(payment, settings, tx_details: dict, *, unit: str, price_line: str, tx_hash: str) -> None:
    """Credit the invoice once, then notify the user (unless direct-pay took over) and the log channel."""

    def asset_lines(paid) -> list[str]:
        network = (paid.arz or "").upper()
        return [f"<b>💎 مقدار {unit}:</b> <code>{paid.amount}</code> {unit}", f"<b>🧬 شبکه:</b> <code>{network}</code>"]

    def user_text(paid, bonus, total_amount, new_amount) -> str:
        network = (paid.arz or "").upper()
        return _credit_user_text(
            paid,
            new_amount,
            bonus_lines=_bonus_lines(bonus, total_amount, settings),
            asset_lines=[
                f"💎 <b>مقدار {unit}:</b> <code>{paid.amount}</code> {unit}",
                f"🧬 <b>شبکه:</b> <code>{network}</code>",
                price_line,
            ],
        )

    def log_text(paid, bonus, total_amount, new_amount) -> str:
        explorer = tx_details.get("explorer_html") or ""
        return _credit_log_text(
            paid,
            new_amount,
            tx_details,
            bonus_lines=_bonus_lines(bonus, total_amount, settings),
            asset_lines=[*asset_lines(paid), price_line],
            tx_time=_format_tx_time(tx_details.get("timestamp")),
            block_label="بلاک/LT",
            explorer_lines=[explorer] if explorer else [],
        )

    await _credit_and_notify(
        payment, settings, tx_hash, name=payment.arz, log=logger, user_text=user_text, log_text=log_text
    )


async def expire_payment(payment, *, unit: str, price_line: str) -> None:
    network = (payment.arz or "").upper()

    def on_failure(e: Exception) -> None:
        logger.error("Expire notification failed for order_id=%s: %s", payment.order_id, e)

    await _expire_and_notify(
        payment,
        user_text=lambda: _expire_user_text(
            payment,
            [
                f"<b>💰 مقدار {unit}:</b> <code>{payment.amount}</code> {unit}",
                f"<b>🧬 شبکه:</b> <code>{network}</code>",
                price_line,
            ],
        ),
        log_text=lambda: _expire_log_text(
            payment,
            [f"💰 مقدار {unit}: <code>{payment.amount}</code>", f"🧬 شبکه: {network}"],
            network.lower().replace("-", "_"),
        ),
        on_failure=on_failure,
    )


# ---------------------------------------------------------------------------
# Price-listing notices (TRX, TON, USDT-TRC20)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PriceRow:
    label: str
    setting: str

    def value(self, settings) -> str:
        return f"{getattr(settings, self.setting):,}"


@dataclass(frozen=True)
class PricedNotice:
    """Texts of a chain whose notices list asset prices and its own explorer link."""

    name: str
    amount_label: str
    unit: str
    confirm_prices: tuple[PriceRow, ...]
    expire_prices: tuple[PriceRow, ...]
    explorer_line: str  # formatted with ``hash``
    timestamp_in_ms: bool
    tag: str
    log: logging.Logger


def _priced_tx_time(timestamp, *, in_ms: bool) -> str:
    if not timestamp:
        return "N/A"
    try:
        return datetime.fromtimestamp(timestamp / 1000 if in_ms else timestamp, tz=UTC).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )
    except Exception:
        return "N/A"


async def confirm_priced_payment(payment, settings, tx_details: dict, *, tx_hash: str, notice: PricedNotice) -> None:
    def user_text(paid, bonus, total_amount, new_amount) -> str:
        return _credit_user_text(
            paid,
            new_amount,
            bonus_lines=_bonus_lines(bonus, total_amount, settings),
            asset_lines=[
                f"💎 <b>مقدار {notice.amount_label}:</b> <code>{paid.amount}</code> {notice.unit}",
                *(
                    f"📊 <b>قیمت {row.label}:</b> <code>{row.value(settings)}</code> هزارتومان"
                    for row in notice.confirm_prices
                ),
            ],
        )

    def log_text(paid, bonus, total_amount, new_amount) -> str:
        return _credit_log_text(
            paid,
            new_amount,
            tx_details,
            bonus_lines=_bonus_lines(bonus, total_amount, settings, bold_emoji=True),
            asset_lines=[
                f"<b>💎 مقدار {notice.amount_label}:</b> <code>{paid.amount}</code> {notice.unit}",
                *(
                    f"<b>📊 قیمت {row.label}:</b> <code>{row.value(settings)}</code> هزارتومان"
                    for row in notice.confirm_prices
                ),
            ],
            tx_time=_priced_tx_time(tx_details["timestamp"], in_ms=notice.timestamp_in_ms),
            block_label="شماره بلاک",
            explorer_lines=[notice.explorer_line.format(hash=tx_details["hash"])],
        )

    await _credit_and_notify(
        payment, settings, tx_hash, name=notice.name, log=notice.log, user_text=user_text, log_text=log_text
    )


async def expire_priced_payment(payment, settings, *, notice: PricedNotice) -> None:
    def on_failure(e: Exception) -> None:
        if isinstance(e, errors.UserIsBlockedError):
            notice.log.debug(
                "%s expire notice skipped, user blocked the bot: order_id=%s", notice.name, payment.order_id
            )
        else:
            notice.log.exception("%s expire notification failed for order_id=%s", notice.name, payment.order_id)

    await _expire_and_notify(
        payment,
        user_text=lambda: _expire_user_text(
            payment,
            [
                f"<b>💰 مقدار {notice.amount_label}:</b> <code>{payment.amount}</code> {notice.unit}",
                *(
                    f"<b>📊 قیمت {row.label}:</b> <code>{row.value(settings)}</code> <b>هزارتومان</b>"
                    for row in notice.expire_prices
                ),
            ],
        ),
        log_text=lambda: _expire_log_text(
            payment,
            [
                f"💰 مقدار {notice.amount_label}: <code>{payment.amount}</code>",
                *(
                    f"📊 قیمت {row.label}: <code>{row.value(settings)}</code> هزار تومان"
                    for row in notice.expire_prices
                ),
            ],
            notice.tag,
        ),
        on_failure=on_failure,
    )
