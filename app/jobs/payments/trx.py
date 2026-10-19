"""
TRX Payment Processor

This processor handles checking and confirming TRX (Tron) cryptocurrency payments.
"""

import logging

import httpx

from app.db.crud.cryptopayments import CryptoPaymentsCRUD
from app.db.crud.settings import SettingsManager
from app.db.crud.wallets import WalletCRUD
from app.logger import get_logger
from config import TRX_TESTNET_MODE

from .base import BasePaymentProcessor
from .crypto_common import (
    PricedNotice,
    PriceRow,
    amount_matches,
    confirm_priced_payment,
    expire_priced_payment,
    expire_unmatched,
    match_transfers,
    tx_time_in_window,
)
from .tx_id import chain_tx_id

logger = get_logger(__name__)

TRONSCAN_EXPLORER_LINE = (
    "<b>🔗 مشاهده در TronScan:</b> <a href='https://tronscan.org/#/transaction/{hash}'>لینک تراکنش</a>"
)
NOTICE = PricedNotice(
    name="TRX",
    amount_label="ترون",
    unit="TRX",
    confirm_prices=(PriceRow("ترون", "arz_trx"), PriceRow("دلار", "arz_usd")),
    expire_prices=(PriceRow("دلار", "arz_usd"), PriceRow("ترون", "arz_trx")),
    explorer_line=TRONSCAN_EXPLORER_LINE,
    timestamp_in_ms=True,
    tag="trx",
    log=logger,
)


def tronscan_base_url(mode: str | None, label: str, address_wallet: str, log: logging.Logger) -> str:
    """TronScan API host for the configured TRX network (shared by TRX and USDT-TRC20)."""
    if mode == "nile":
        log.debug("🔧 %s Testnet mode: Nile Testnet - Address: %s", label, address_wallet)
        return "https://nileapi.tronscan.org"
    if mode == "shasta":
        log.debug("🔧 %s Testnet mode: Shasta Testnet - Address: %s", label, address_wallet)
        return "https://shastapi.tronscan.org"
    return "https://apilist.tronscanapi.com"


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


_NATIVE_TRX_TOKEN_ID = "_"
_TRANSFER_CONTRACT_TYPE = 1


def is_native_trx_transfer(transaction: dict) -> bool:
    """True only for a successful native TRX transfer.

    TronScan reports TRC10 tokens with the same ``amount`` field and no contract
    ``address``, so the token id is the only reliable marker: native TRX is ``"_"``.
    """
    contract_type = transaction.get("contractType")
    if contract_type is not None and int(contract_type) != _TRANSFER_CONTRACT_TYPE:
        return False
    contract_ret = transaction.get("contractRet")
    if contract_ret is not None and contract_ret != "SUCCESS":
        return False
    if transaction.get("revert") is True:
        return False
    token_info = transaction.get("tokenInfo")
    if isinstance(token_info, dict):
        return str(token_info.get("tokenId")) == _NATIVE_TRX_TOKEN_ID
    return token_info is None and contract_type is not None


async def extract_tronscan_amount(transaction, decimals=6):
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
        base_url = tronscan_base_url(TRX_TESTNET_MODE, "TRX", address_wallet, logger)

        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {"TRON-PRO-API-KEY": api_key} if api_key else {}
            crud = CryptoPaymentsCRUD()
            valid_payments = await crud.get_pending_by_arz("TRX")
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
            consumed = await crud.get_used_tx_hashes(chain_tx_id(tx) for tx in all_transactions)

            def candidates(payment):
                transactions_found = [
                    tx
                    for tx in all_transactions
                    if tx_time_in_window(payment, tx.get("timestamp") or tx.get("block_timestamp"))
                ]
                if not transactions_found:
                    return
                logger.debug("Processing %s TRX txs for payment %s", len(transactions_found), payment.order_id)
                for transaction in transactions_found:
                    tx_to = transaction.get("to") or transaction.get("toAddress") or transaction.get("ownerAddress")
                    if tx_to and tx_to.lower() != address_wallet.lower():
                        continue
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
                name="TRX",
                error_message="Error processing TRX payment %s: %s",
                log=logger,
                retry_after_error=True,
            )

            await expire_unmatched(valid_payments, matched, lambda payment: self._expire_payment(payment, settings))

    async def _validate_transaction(self, transaction, payment_amount, address_wallet):
        if not is_native_trx_transfer(transaction):
            return False
        amount_in_trx = await extract_tronscan_amount(transaction, decimals=6)
        if amount_in_trx is None:
            return False
        return amount_matches(payment_amount, amount_in_trx)

    async def _expire_payment(self, payment, settings):
        await expire_priced_payment(payment, settings, notice=NOTICE)
