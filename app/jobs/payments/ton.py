"""
TON Payment Processor

This processor handles checking and confirming TON (Toncoin) cryptocurrency payments.
"""

from decimal import Decimal

import httpx

from app.db.crud.cryptopayments import CryptoPaymentsCRUD
from app.db.crud.settings import SettingsManager
from app.db.crud.wallets import WalletCRUD
from app.logger import get_logger
from config import TON_TESTNET_MODE

from .base import BasePaymentProcessor
from .crypto_common import (
    PricedNotice,
    PriceRow,
    confirm_priced_payment,
    expire_priced_payment,
    expire_unmatched,
    match_transfers,
    tx_time_in_window,
)
from .tx_id import chain_tx_id

logger = get_logger(__name__)

NOTICE = PricedNotice(
    name="TON",
    amount_label="TON",
    unit="TON",
    confirm_prices=(PriceRow("TON", "arz_ton"), PriceRow("دلار", "arz_usd")),
    expire_prices=(PriceRow("TON", "arz_ton"), PriceRow("دلار", "arz_usd")),
    explorer_line="<b>🔗 مشاهده در TON Explorer:</b> <a href='https://tonscan.org/tx/{hash}'>لینک تراکنش</a>",
    timestamp_in_ms=False,
    tag="ton",
    log=logger,
)


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
            valid_payments = await crud.get_pending_by_arz("TON")
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
            consumed = await crud.get_used_tx_hashes(chain_tx_id(tx) for tx in all_transactions)

            def candidates(payment):
                logger.debug(
                    "Checking TON payment %s amount=%s createtime=%s",
                    payment.order_id,
                    payment.amount,
                    payment.createtime,
                )
                payment_transactions = [tx for tx in all_transactions if tx_time_in_window(payment, tx.get("utime"))]
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
                    yield transaction

            matched = await match_transfers(
                valid_payments,
                candidates,
                consumed,
                tx_id=chain_tx_id,
                accepts=lambda payment, tx: self._validate_transaction(tx, payment.amount, address_wallet),
                confirm=lambda payment, tx, txid: confirm_priced_payment(
                    payment, settings, _extract_transaction_details(tx, address_wallet), tx_hash=txid, notice=NOTICE
                ),
                name="TON",
                error_message="Error processing TON payment %s: %s",
                log=logger,
                retry_after_error=True,
            )

            await expire_unmatched(valid_payments, matched, lambda payment: self._expire_payment(payment, settings))

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
        await expire_priced_payment(payment, settings, notice=NOTICE)
