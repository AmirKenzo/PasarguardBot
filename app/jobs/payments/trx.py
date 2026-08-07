"""
TRX Payment Processor

This processor handles checking and confirming TRX (Tron) cryptocurrency payments.
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
from config import TRX_TESTNET_MODE

from .base import BasePaymentProcessor

logger = get_logger(__name__)


async def _fetch_trx_transactions(client, base_url, headers, address_wallet, start_time, order_id):
    """
    Fetch native TRX transactions from TronScan API.

    Strategy:
    - First try /api/transaction (returns all transaction types including native TRX)
    - If no results, try /api/new/transfer (returns transfer transactions)
    """
    transactions_found = []
    seen_hashes = set()

    # Method 1: Try /api/transaction first
    try:
        url1 = f"{base_url}/api/transaction"
        params1 = {"limit": 50, "address": address_wallet, "start_timestamp": start_time}
        response1 = await client.get(url1, headers=headers, params=params1, timeout=30.0)
        if response1.status_code == 200:
            data1 = response1.json()
            if data1.get("data"):
                count = 0
                for tx in data1["data"]:
                    tx_hash = tx.get("hash") or tx.get("transactionHash")
                    if tx_hash and tx_hash not in seen_hashes:
                        seen_hashes.add(tx_hash)
                        transactions_found.append(tx)
                        count += 1
                if count > 0:
                    logger.debug(f"Found {count} transactions from /api/transaction for payment {order_id}")
                    return transactions_found
    except Exception as e:
        logger.error(f"Failed to fetch from /api/transaction for payment {order_id}: {e}")

    # Method 2: Fallback to /api/new/transfer
    try:
        url2 = f"{base_url}/api/new/transfer"
        params2 = {"limit": 50, "address": address_wallet, "start_timestamp": start_time, "toAddress": address_wallet}
        response2 = await client.get(url2, headers=headers, params=params2, timeout=30.0)
        if response2.status_code == 200:
            data2 = response2.json()
            if data2.get("data"):
                count = 0
                for tx in data2["data"]:
                    tx_hash = tx.get("hash") or tx.get("transactionHash")
                    if tx_hash and tx_hash not in seen_hashes:
                        seen_hashes.add(tx_hash)
                        transactions_found.append(tx)
                        count += 1
                if count > 0:
                    logger.debug(f"Found {count} transactions from /api/new/transfer for payment {order_id}")
    except Exception as e:
        logger.error(f"Failed to fetch from /api/new/transfer for payment {order_id}: {e}")

    return transactions_found


async def _extract_transaction_amount(transaction, decimals=6):
    amount = (
        transaction.get("amount")
        or transaction.get("amount_str")
        or transaction.get("value")
        or transaction.get("quant")
        or 0
    )
    if isinstance(amount, str):
        try:
            amount = float(amount)
        except ValueError:
            amount = 0
    if not amount or amount == 0:
        return None
    return float(amount) / (10**decimals)


def _extract_transaction_details(transaction, address_wallet):
    return {
        "hash": transaction.get("hash") or transaction.get("transactionHash", "N/A"),
        "from": (transaction.get("from") or transaction.get("fromAddress") or transaction.get("ownerAddress") or "N/A"),
        "to": (
            transaction.get("to") or transaction.get("toAddress") or transaction.get("ownerAddress") or address_wallet
        ),
        "timestamp": transaction.get("timestamp") or transaction.get("block_timestamp") or 0,
        "block": transaction.get("block") or transaction.get("blockNumber") or "N/A",
        "confirmed": transaction.get("confirmed", False),
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
            f"💎 <b>مقدار ترون:</b> <code>{payment.amount}</code> TRX",
            f"📊 <b>قیمت ترون:</b> <code>{settings.arz_trx:,}</code> هزارتومان",
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
            tx_time = datetime.fromtimestamp(tx_details["timestamp"] / 1000, tz=UTC)
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
            f"<b>💎 مقدار ترون:</b> <code>{payment.amount}</code> TRX",
            f"<b>📊 قیمت ترون:</b> <code>{settings.arz_trx:,}</code> هزارتومان",
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
            f"<b>🔗 مشاهده در TronScan:</b> "
            f"<a href='https://tronscan.org/#/transaction/{tx_details['hash']}'>لینک تراکنش</a>",
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
        logger.warning("TRX payment already processed or invalid: order_id=%s", payment.order_id)
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


class TRXProcessor(BasePaymentProcessor):
    def __init__(self):
        super().__init__("trx")

    async def check_payments(self):
        settings = await SettingsManager().get_settings()

        # Get wallet from database
        wallet = await WalletCRUD().get_wallet_by_type("TRX")
        if not wallet:
            logger.debug("TRX wallet not configured — skipping payment check")
            return

        address_wallet = wallet.address
        api_key = wallet.api_key or ""

        # Check testnet mode
        if TRX_TESTNET_MODE == "nile":
            base_url = "https://nileapi.tronscan.org"
            logger.debug(f"🔧 TRX Testnet mode: Nile Testnet - Address: {address_wallet}")
        elif TRX_TESTNET_MODE == "shasta":
            base_url = "https://shastapi.tronscan.org"
            logger.debug(f"🔧 TRX Testnet mode: Shasta Testnet - Address: {address_wallet}")
        else:
            base_url = "https://apilist.tronscanapi.com"

        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {"TRON-PRO-API-KEY": api_key} if api_key else {}
            crud = CryptoPaymentsCRUD()
            pending_payments = await crud.get_pending_by_arz("TRX")

            valid_payments = []
            for payment in pending_payments:
                created_time = datetime.fromtimestamp(payment.createtime, tz=UTC)
                time_diff = datetime.now(UTC) - created_time
                if time_diff > timedelta(minutes=30):
                    await self._expire_payment(payment, settings)
                else:
                    valid_payments.append(payment)

            if not valid_payments:
                return

            earliest_ms = min(payment.createtime for payment in valid_payments) * 1000
            logger.info(
                "Fetching TRX txs for %s pending payments from start_ms=%s address=%s",
                len(valid_payments),
                earliest_ms,
                address_wallet,
            )
            all_transactions = await _fetch_trx_transactions(
                client, base_url, headers, address_wallet, earliest_ms, "batch"
            )

            for payment in valid_payments:
                start_ms = payment.createtime * 1000
                transactions_found = [
                    tx
                    for tx in all_transactions
                    if int(tx.get("timestamp") or tx.get("block_timestamp") or 0) >= start_ms
                ]
                if not transactions_found:
                    continue

                logger.debug(
                    "Processing %s TRX txs for payment %s",
                    len(transactions_found),
                    payment.order_id,
                )
                for transaction in transactions_found:
                    tx_to = transaction.get("to") or transaction.get("toAddress") or transaction.get("ownerAddress")
                    if tx_to and tx_to.lower() != address_wallet.lower():
                        continue
                    if not await self._validate_transaction(transaction, payment.amount, address_wallet):
                        continue

                    paytime = int(datetime.now(UTC).timestamp())
                    try:
                        await _process_payment_confirmation(payment, settings, transaction, address_wallet, paytime)
                        break
                    except Exception as e:
                        logger.error("Error processing TRX payment %s: %s", payment.order_id, e)

    async def _validate_transaction(self, transaction, payment_amount, address_wallet):
        token_info = transaction.get("tokenInfo")
        is_native_trx = not token_info or (
            isinstance(token_info, dict) and (not token_info.get("address") or token_info.get("symbol") == "TRX")
        )
        if not is_native_trx:
            return False
        amount_in_trx = await _extract_transaction_amount(transaction, decimals=6)
        if amount_in_trx is None:
            return False

        payment_amount_decimal = Decimal(str(payment_amount)).quantize(Decimal("0.000001"))
        trx_amount_decimal = Decimal(str(amount_in_trx)).quantize(Decimal("0.000001"))

        return abs(payment_amount_decimal - trx_amount_decimal) <= Decimal("0.000001")

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
                f"<b>💰 مقدار ترون:</b> <code>{payment.amount}</code> TRX\n"
                f"<b>📊 قیمت دلار:</b> <code>{settings.arz_usd:,}</code> <b>هزارتومان</b>\n"
                f"<b>📊 قیمت ترون:</b> <code>{settings.arz_trx:,}</code> <b>هزارتومان</b>\n"
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
                f"💰 مقدار ترون: <code>{payment.amount}</code>\n"
                f"📊 قیمت دلار: <code>{settings.arz_usd:,}</code> هزار تومان\n"
                f"📊 قیمت ترون: <code>{settings.arz_trx:,}</code> هزار تومان\n"
                f"#trx_{payment.order_id}"
            )
            await send_log_message(LogType.CRYPTO, message=log_text, parse_mode="html")
        except Exception:
            pass
