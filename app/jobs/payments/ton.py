"""
TON Payment Processor

This processor handles checking and confirming TON (Toncoin) cryptocurrency payments.
"""

import contextlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
from telethon import Button

from app import Kenzo
from app.db.crud.cryptopayments import CryptoPaymentsCRUD
from app.db.crud.settings import SettingsManager
from app.db.crud.wallets import WalletCRUD
from app.logger import LogType, get_logger
from app.services.billing.direct_pay_fulfillment import (
    cancel_after_crypto_expire,
    try_fulfill_after_crypto_credit,
)
from app.services.billing.payment_bonus import calculate_payment_bonus
from app.telegram.shared.utils.logging import send_log_message
from config import TON_TESTNET_MODE

from .base import BasePaymentProcessor

logger = get_logger(__name__)


async def _fetch_ton_transactions(client, base_url, address_wallet, start_time, order_id=None):
    """
    Fetch TON transactions from TonCenter API.

    TON uses nanoTONs (1 TON = 1,000,000,000 nanoTONs)
    """
    transactions_found = []
    seen_hashes = set()

    try:
        # TonCenter API: getTransactions
        # https://toncenter.com/api/v2/getTransactions?address=...
        url = f"{base_url}/getTransactions"
        params = {"address": address_wallet, "limit": 50, "archival": True}

        logger.debug(f"TonCenter API request: {url}, params: {params}")
        response = await client.get(url, params=params, timeout=30.0)
        logger.debug(f"TonCenter API response status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            logger.info(
                f"TonCenter API response structure: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}"
            )

            if data.get("ok"):
                transactions = data.get("result", [])
                logger.debug(f"Found {len(transactions)} transactions in response")

                for tx in transactions:
                    tx_id = tx.get("transaction_id", {})
                    tx_hash = tx_id.get("hash") if isinstance(tx_id, dict) else str(tx_id) if tx_id else tx.get("hash")

                    if tx_hash and tx_hash not in seen_hashes:
                        seen_hashes.add(tx_hash)
                        transactions_found.append(tx)

                if transactions_found:
                    logger.info(
                        f"✅ Found {len(transactions_found)} unique transactions from TonCenter for payment {order_id}"
                    )
                    return transactions_found
            else:
                error = data.get("error", "Unknown error")
                logger.error(f"TonCenter API returned error: {error}")
    except Exception as e:
        logger.error(f"Failed to fetch from TonCenter API for payment {order_id}: {e}")

    return transactions_found


async def _extract_transaction_amount(transaction):
    """
    Extract TON amount from TonCenter API transaction.
    TON uses nanoTONs (1 TON = 1,000,000,000 nanoTONs = 1e9)
    """
    logger.debug("🔍 _extract_transaction_amount called")
    logger.debug(f"Transaction keys: {list(transaction.keys())}")

    # TonCenter API structure: transaction.in_msg.value
    in_msg = transaction.get("in_msg")
    if in_msg:
        amount = in_msg.get("value")
        logger.debug(f"in_msg.value: {amount}")

        if amount:
            # Amount is in nanoTONs, convert to TON
            if isinstance(amount, str):
                try:
                    amount = int(amount)
                except ValueError:
                    logger.error(f"Failed to convert amount string to int: {amount}")
                    return None

            if amount and amount > 0:
                # Use Decimal for precise calculation
                ton_amount = Decimal(str(amount)) / Decimal("1000000000")
                logger.debug(f"Converted {amount} nanoTONs to {ton_amount} TON")
                return float(ton_amount)

    logger.error("❌ Amount not found in transaction")
    return None


def _extract_transaction_details(transaction, address_wallet):
    in_msg = transaction.get("in_msg") or {}
    return {
        "hash": transaction.get("hash")
        or transaction.get("transaction_id")
        or transaction.get("transaction_hash", "N/A"),
        "from": in_msg.get("source") or in_msg.get("source_address") or transaction.get("from") or "N/A",
        "to": in_msg.get("destination") or in_msg.get("destination_address") or transaction.get("to") or address_wallet,
        "timestamp": transaction.get("utime") or transaction.get("now") or transaction.get("timestamp") or 0,
        "block": transaction.get("block") or transaction.get("block_seqno") or "N/A",
        "confirmed": transaction.get("confirmed", True),
    }


def _format_user_payment_message(payment, settings, bonus, total_amount, new_amount):
    msg_parts = [
        "🎉 <b>پرداخت شما با موفقیت انجام شد!</b>",
        "",
        f"📋 <b>شماره فاکتور:</b> <code>{payment.order_id}</code>",
        f"💵 <b>مبلغ:</b> <code>{int(payment.amount_irt):,}</code> تومان",
    ]

    if bonus > 0:
        msg_parts.extend(
            [
                f"🎁 <b>بونوس:</b> +<code>{int(bonus):,}</code> تومان ({settings.crypto_bonus_percent}%)",
                f"💰 <b>مجموع:</b> <code>{int(total_amount):,}</code> تومان",
            ]
        )

    msg_parts.extend(
        [
            f"💎 <b>مقدار TON:</b> <code>{payment.amount}</code> TON",
            f"📊 <b>قیمت TON:</b> <code>{settings.arz_ton:,}</code> هزارتومان",
            f"📊 <b>قیمت دلار:</b> <code>{settings.arz_usd:,}</code> هزارتومان",
            "",
            f"💳 <b>موجودی جدید:</b> <code>{int(new_amount):,}</code> تومان",
            "",
            f"<code>#{payment.arz}_{payment.order_id}</code>",
        ]
    )

    return "\n".join(msg_parts)


def _format_admin_log_message(payment, settings, bonus, total_amount, new_amount, tx_details):
    tx_time_str = "N/A"
    if tx_details["timestamp"]:
        try:
            tx_time = datetime.fromtimestamp(tx_details["timestamp"], tz=UTC)
            tx_time_str = tx_time.strftime("%Y-%m-%d %H:%M:%S UTC")
        except Exception:
            pass

    log_parts = [
        "#فاکتور_ارزی",
        "<b>✅ فاکتور ارزی کاربر با موفقیت پرداخت شد</b>",
        "",
        f"<b>👤 شناسه کاربری:</b> <code>{payment.user_id}</code> | "
        f"<a href='tg://user?id={payment.user_id}'>پروفایل کاربر</a>",
        f"<b>📋 شماره فاکتور:</b> <code>{payment.order_id}</code>",
        f"<b>💵 مبلغ فاکتور:</b> <code>{int(payment.amount_irt):,}</code> تومان",
    ]

    if bonus > 0:
        log_parts.extend(
            [
                f"<b>🎁 بونوس:</b> +<code>{int(bonus):,}</code> تومان ({settings.crypto_bonus_percent}%)",
                f"<b>💰 مجموع:</b> <code>{int(total_amount):,}</code> تومان",
            ]
        )

    log_parts.extend(
        [
            f"<b>💎 مقدار TON:</b> <code>{payment.amount}</code> TON",
            f"<b>📊 قیمت TON:</b> <code>{settings.arz_ton:,}</code> هزارتومان",
            f"<b>📊 قیمت دلار:</b> <code>{settings.arz_usd:,}</code> هزارتومان",
            f"<b>💳 موجودی جدید کاربر:</b> <code>{int(new_amount):,}</code> تومان",
            "",
            "<b>🔗 جزئیات تراکنش بلاکچین:</b>",
            f"<b>📝 هش تراکنش:</b> <code>{tx_details['hash']}</code>",
            f"<b>👤 از آدرس:</b> <code>{tx_details['from']}</code>",
            f"<b>👥 به آدرس:</b> <code>{tx_details['to']}</code>",
            f"<b>⏰ زمان تراکنش:</b> <code>{tx_time_str}</code>",
            f"<b>📦 شماره بلاک:</b> <code>{tx_details['block']}</code>",
            f"<b>✅ وضعیت:</b> {'تایید شده' if tx_details['confirmed'] else 'در انتظار تایید'}",
            f"<b>🔗 مشاهده در TON Explorer:</b> <a href='https://tonscan.org/tx/{tx_details['hash']}'>لینک تراکنش</a>",
            "",
            f"<code>#{payment.arz}_{payment.order_id}</code>",
        ]
    )

    return "\n".join(log_parts)


async def _process_payment_confirmation(payment, settings, transaction, address_wallet, paytime: int):
    tx_details = _extract_transaction_details(transaction, address_wallet)

    bonus = await calculate_payment_bonus(
        amount=int(payment.amount_irt),
        bonus_enabled=settings.crypto_bonus_enabled,
        bonus_percent=settings.crypto_bonus_percent,
    )
    total_amount = int(payment.amount_irt) + bonus
    approved = await CryptoPaymentsCRUD().approve_and_credit(payment.order_id, total_amount, paytime)
    if not approved:
        logger.warning("TON payment already processed or invalid: order_id=%s", payment.order_id)
        return
    payment, new_amount = approved
    fulfilled = await try_fulfill_after_crypto_credit(int(payment.order_id))
    if not fulfilled:
        user_msg = _format_user_payment_message(payment, settings, bonus, total_amount, new_amount)
        await Kenzo.send_message(
            payment.user_id,
            user_msg,
            parse_mode="html",
            buttons=[
                [
                    Button.inline(
                        text=f"💳 موجودی: {int(new_amount):,} تومان",
                        data="no_action",
                    )
                ]
            ],
        )

    admin_log = _format_admin_log_message(payment, settings, bonus, total_amount, new_amount, tx_details)
    await send_log_message(
        LogType.CRYPTO,
        message=admin_log,
        parse_mode="html",
        buttons=[
            [
                Button.inline(
                    text=f"💳 موجودی: {int(new_amount):,} تومان",
                    data="no_action",
                )
            ]
        ],
    )


class TONProcessor(BasePaymentProcessor):
    def __init__(self):
        super().__init__("ton")

    async def check_payments(self):
        settings = await SettingsManager().get_settings()

        wallet = await WalletCRUD().get_wallet_by_type("TON")
        if not wallet:
            logger.debug("TON wallet not configured — skipping payment check")
            return

        address_wallet = wallet.address
        # TonCenter API doesn't require API key (optional)

        # Check testnet mode - use TonCenter API
        if TON_TESTNET_MODE == "testnet":
            base_url = "https://testnet.toncenter.com/api/v2"
            logger.debug(f"🔧 TON Testnet mode: Testnet - Address: {address_wallet}")
        else:
            base_url = "https://toncenter.com/api/v2"

        async with httpx.AsyncClient(timeout=30.0) as client:
            crud = CryptoPaymentsCRUD()
            pending_payments = await crud.get_pending_by_arz("TON")

            if not pending_payments:
                return

            # Expire old payments first
            current_time = datetime.now(UTC)
            valid_payments = []
            for payment in pending_payments:
                created_time = datetime.fromtimestamp(payment.createtime, tz=UTC)
                time_diff = current_time - created_time

                if time_diff > timedelta(minutes=30):
                    await self._expire_payment(payment, settings)
                else:
                    valid_payments.append(payment)

            if not valid_payments:
                return

            # Find the earliest payment time to fetch transactions from
            earliest_time = min(payment.createtime for payment in valid_payments)
            logger.info(
                "Fetching TON txs for %s pending payments, earliest=%s",
                len(valid_payments),
                earliest_time,
            )

            # Fetch all transactions once
            all_transactions = await _fetch_ton_transactions(client, base_url, address_wallet, earliest_time, None)
            logger.debug("Fetched %s total transactions from TonCenter", len(all_transactions))

            # Process each payment with the fetched transactions
            for payment in valid_payments:
                logger.debug(
                    "Checking TON payment %s amount=%s createtime=%s",
                    payment.order_id,
                    payment.amount,
                    payment.createtime,
                )

                # Filter transactions for this specific payment (after payment creation time)
                payment_transactions = [tx for tx in all_transactions if tx.get("utime", 0) >= payment.createtime]
                logger.debug(
                    "Found %s TON txs after createtime for payment %s",
                    len(payment_transactions),
                    payment.order_id,
                )

                for transaction in payment_transactions:
                    in_msg = transaction.get("in_msg", {})
                    tx_destination = in_msg.get("destination", "") if isinstance(in_msg, dict) else ""
                    logger.debug(
                        "TON tx destination=%s wallet=%s payment=%s",
                        tx_destination,
                        address_wallet,
                        payment.order_id,
                    )

                    is_valid = await self._validate_transaction(transaction, payment.amount, address_wallet)
                    if not is_valid:
                        continue

                    paytime = int(datetime.now(UTC).timestamp())
                    try:
                        await _process_payment_confirmation(payment, settings, transaction, address_wallet, paytime)
                        break
                    except Exception as e:
                        logger.error("Error processing TON payment %s: %s", payment.order_id, e)

    async def _validate_transaction(self, transaction, payment_amount, address_wallet):
        logger.debug("TON validate payment_amount=%s", payment_amount)

        amount_in_ton = await _extract_transaction_amount(transaction)
        if amount_in_ton is None:
            logger.debug("TON amount extraction failed for tx=%s", transaction.get("transaction_id"))
            return False

        payment_amount_decimal = Decimal(str(payment_amount)).quantize(Decimal("0.000000000001"))
        ton_amount_decimal = Decimal(str(amount_in_ton)).quantize(Decimal("0.000000000001"))
        logger.debug("TON compare payment=%s tx=%s", payment_amount_decimal, ton_amount_decimal)

        # Exact match required - no tolerance
        is_valid = payment_amount_decimal == ton_amount_decimal
        if not is_valid:
            difference = abs(payment_amount_decimal - ton_amount_decimal)
            logger.debug(
                "TON amount mismatch payment=%s tx=%s diff=%s",
                payment_amount_decimal,
                ton_amount_decimal,
                difference,
            )
        return is_valid

    async def _expire_payment(self, payment, settings):
        crud = CryptoPaymentsCRUD()
        await crud.expire_payment(payment.order_id)
        await cancel_after_crypto_expire(int(payment.order_id))

        try:
            if hasattr(payment, "msg_id") and payment.msg_id:
                with contextlib.suppress(Exception):
                    await Kenzo.delete_messages(payment.user_id, payment.msg_id)

            expire_msg = (
                f"<b>#اطلاع_رسانی</b>\n\n"
                f"<b>📅 فاکتور شماره [ {payment.order_id} ] به دلیل گذشتن زمان منقضی شد.</b>\n"
                f"<b>💵 مبلغ فاکتور:</b> <code>{int(payment.amount_irt):,}</code> <b>تومان</b>\n"
                f"<b>💰 مقدار TON:</b> <code>{payment.amount}</code> TON\n"
                f"<b>📊 قیمت TON:</b> <code>{settings.arz_ton:,}</code> <b>هزارتومان</b>\n"
                f"<b>📊 قیمت دلار:</b> <code>{settings.arz_usd:,}</code> <b>هزارتومان</b>\n"
                f"<b>#notification_{payment.order_id}</b>"
            )
            await Kenzo.send_message(
                payment.user_id,
                expire_msg,
                parse_mode="html",
                buttons=[[Button.inline(text="🚫 منقضی شد", data="no_action")]],
            )

            log_text = (
                "#فاکتور_منقضی\n"
                f"👤 شناسه کاربر: <code>{payment.user_id}</code> | "
                f"<a href='tg://user?id={payment.user_id}'>پروفایل کاربر</a>\n"
                f"💡 شماره فاکتور: <code>{payment.order_id}</code>\n"
                f"💵 مبلغ فاکتور: <code>{int(payment.amount_irt):,}</code> تومان\n"
                f"💰 مقدار TON: <code>{payment.amount}</code>\n"
                f"📊 قیمت TON: <code>{settings.arz_ton:,}</code> هزار تومان\n"
                f"📊 قیمت دلار: <code>{settings.arz_usd:,}</code> هزار تومان\n"
                f"#ton_{payment.order_id}"
            )
            await send_log_message(LogType.CRYPTO, message=log_text, parse_mode="html")
        except Exception:
            pass
