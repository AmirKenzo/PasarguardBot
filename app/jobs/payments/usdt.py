"""
USDT Payment Processor

This processor handles checking and confirming USDT (TRC20) cryptocurrency payments.
"""

from decimal import Decimal

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
    confirm_priced_payment,
    expire_priced_payment,
    expire_unmatched,
    match_transfers,
    to_unix_seconds,
    tx_time_in_window,
)
from .trx import TRONSCAN_EXPLORER_LINE, extract_tronscan_amount, tronscan_base_url
from .tx_id import chain_tx_id

logger = get_logger(__name__)

# USDT contract address (mainnet)
USDT_CONTRACT_MAINNET = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
NOTICE = PricedNotice(
    name="USDT",
    amount_label="USDT",
    unit="USDT",
    confirm_prices=(PriceRow("دلار", "arz_usd"),),
    expire_prices=(PriceRow("دلار", "arz_usd"),),
    explorer_line=TRONSCAN_EXPLORER_LINE,
    timestamp_in_ms=True,
    tag="usdt",
    log=logger,
)


async def _fetch_token_transfers(client, base_url, headers, address_wallet, start_time, order_id, token_contract=None):
    """
    Fetch token transfers (like USDT) from TronScan API.
    Works with both mainnet and testnet (Nile/Shasta).
    """
    transactions_found = []
    seen_hashes = set()

    # Method 1: Try /api/new/transfer first
    try:
        url1 = f"{base_url}/api/new/transfer"
        params1 = {
            "limit": 50,
            "address": address_wallet,
            "start_timestamp": start_time,
            "toAddress": address_wallet,
        }
        response1 = await client.get(url1, headers=headers, params=params1, timeout=30.0)
        if response1.status_code == 200:
            data1 = response1.json()
            if data1.get("data"):
                count = 0
                for tx in data1["data"]:
                    tx_hash = tx.get("hash") or tx.get("transactionHash")
                    if tx_hash and tx_hash not in seen_hashes:
                        token_info = tx.get("tokenInfo")
                        if token_info:
                            tx_to = tx.get("to") or tx.get("toAddress") or tx.get("ownerAddress")
                            if tx_to and tx_to.lower() == address_wallet.lower():
                                seen_hashes.add(tx_hash)
                                transactions_found.append(tx)
                                count += 1
                if count > 0:
                    logger.debug(f"Found {count} token transfers from /api/new/transfer for payment {order_id}")
                    return transactions_found
    except Exception as e:
        logger.error(f"Failed to fetch from /api/new/transfer for payment {order_id}: {e}")

    # Method 2: Try /api/token_trc20/transfers
    try:
        url2 = f"{base_url}/api/token_trc20/transfers"
        params2 = {
            "limit": 50,
            "start": 0,
            "start_timestamp": start_time,
            "relatedAddress": address_wallet,
        }
        if token_contract:
            params2["contract_address"] = token_contract

        response2 = await client.get(url2, headers=headers, params=params2, timeout=30.0)
        if response2.status_code == 200:
            data2 = response2.json()
            token_transfers = data2.get("token_transfers") or data2.get("data") or []
            if token_transfers:
                count = 0
                for tx in token_transfers:
                    tx_hash = tx.get("transaction_id") or tx.get("hash") or tx.get("transactionHash")
                    if tx_hash and tx_hash not in seen_hashes:
                        to_address = (
                            tx.get("to_address") or tx.get("to") or tx.get("toAddress") or tx.get("to_address_base58")
                        )
                        if to_address and to_address.lower() == address_wallet.lower():
                            seen_hashes.add(tx_hash)
                            transactions_found.append(tx)
                            count += 1
                if count > 0:
                    logger.debug(
                        f"Found {count} token transfers from /api/token_trc20/transfers for payment {order_id}"
                    )
                    return transactions_found
    except Exception as e:
        logger.error(f"Failed to fetch from /api/token_trc20/transfers for payment {order_id}: {e}")

    # Method 3: Try /api/transaction and filter for token transfers
    try:
        url3 = f"{base_url}/api/transaction"
        params3 = {"limit": 50, "address": address_wallet, "start_timestamp": start_time}
        response3 = await client.get(url3, headers=headers, params=params3, timeout=30.0)
        if response3.status_code == 200:
            data3 = response3.json()
            if data3.get("data"):
                count = 0
                for tx in data3["data"]:
                    tx_hash = tx.get("hash") or tx.get("transactionHash")
                    if tx_hash and tx_hash not in seen_hashes:
                        token_info = tx.get("tokenInfo")
                        if token_info:
                            tx_to = tx.get("to") or tx.get("toAddress") or tx.get("ownerAddress")
                            if tx_to and tx_to.lower() == address_wallet.lower():
                                seen_hashes.add(tx_hash)
                                transactions_found.append(tx)
                                count += 1
                if count > 0:
                    logger.debug(f"Found {count} token transfers from /api/transaction for payment {order_id}")
    except Exception as e:
        logger.error(f"Failed to fetch from /api/transaction for payment {order_id}: {e}")

    return transactions_found


def _tx_unix_seconds(transaction: dict) -> int:
    """Transfer time in seconds; /api/token_trc20/transfers rows carry it (in ms) as ``block_ts``."""
    return to_unix_seconds(
        transaction.get("timestamp") or transaction.get("block_timestamp") or transaction.get("block_ts")
    )


def _tx_recipient(transaction: dict) -> str | None:
    return (
        transaction.get("to")
        or transaction.get("toAddress")
        or transaction.get("to_address")
        or transaction.get("ownerAddress")
    )


def _is_successful_transfer(transaction: dict) -> bool:
    for key in ("contractRet", "finalResult"):
        status = transaction.get(key)
        if status is not None and status != "SUCCESS":
            return False
    return transaction.get("revert") is not True


def _extract_transaction_details(transaction, address_wallet):
    return {
        "hash": chain_tx_id(transaction) or "N/A",
        "from": (
            transaction.get("from")
            or transaction.get("fromAddress")
            or transaction.get("from_address")
            or transaction.get("ownerAddress")
            or "N/A"
        ),
        "to": _tx_recipient(transaction) or address_wallet,
        "timestamp": _tx_unix_seconds(transaction) * 1000,
        "block": transaction.get("block") or transaction.get("blockNumber") or "N/A",
        "confirmed": transaction.get("confirmed", False),
    }


class USDTProcessor(BasePaymentProcessor):
    def __init__(self):
        super().__init__("usdt")

    async def check_payments(self):
        settings = await SettingsManager().get_settings()

        # Get wallet from database
        wallet = await WalletCRUD().get_wallet_by_type("USDT")
        if not wallet:
            logger.debug("USDT wallet not configured — skipping payment check")
            return

        address_wallet = wallet.address
        api_key = wallet.api_key or ""
        # Testnet mode uses the TRX testnet config
        base_url = tronscan_base_url(TRX_TESTNET_MODE, "USDT", address_wallet, logger)

        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {"TRON-PRO-API-KEY": api_key} if api_key else {}
            crud = CryptoPaymentsCRUD()
            valid_payments = await crud.get_pending_by_arz("USDT")
            if not valid_payments:
                return

            usdt_contract = USDT_CONTRACT_MAINNET if TRX_TESTNET_MODE is None else None

            earliest_ms = min(payment.createtime for payment in valid_payments) * 1000
            logger.info(
                "Fetching USDT-TRC20 txs for %s pending payments from start_ms=%s",
                len(valid_payments),
                earliest_ms,
            )
            all_transactions = await _fetch_token_transfers(
                client, base_url, headers, address_wallet, earliest_ms, "batch", usdt_contract
            )
            consumed = await crud.get_used_tx_hashes(chain_tx_id(tx) for tx in all_transactions)

            def candidates(payment):
                transactions_found = [tx for tx in all_transactions if tx_time_in_window(payment, _tx_unix_seconds(tx))]
                logger.debug("Found %s token transfers for USDT payment %s", len(transactions_found), payment.order_id)
                if not transactions_found:
                    return
                logger.debug(
                    "Processing %s transactions for USDT payment %s",
                    len(transactions_found),
                    payment.order_id,
                )
                for transaction in transactions_found:
                    tx_to = _tx_recipient(transaction)
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
                name="USDT",
                error_message="Error processing USDT payment %s: %s",
                log=logger,
                retry_after_error=True,
            )

            await expire_unmatched(valid_payments, matched, lambda payment: self._expire_payment(payment, settings))

    async def _validate_transaction(self, transaction, payment_amount, address_wallet):
        token_info = transaction.get("tokenInfo")
        if not token_info:
            return False
        if not _is_successful_transfer(transaction):
            return False

        if TRX_TESTNET_MODE:
            logger.debug(
                "Testnet mode: Accepting token transfer. Token symbol: %s, Contract: %s",
                token_info.get("symbol"),
                token_info.get("address"),
            )
        else:
            token_address = (
                token_info.get("address")
                or token_info.get("contract_address")
                or transaction.get("contract_address")
                or token_info.get("tokenId")
            )
            if not token_address or token_address.upper() != USDT_CONTRACT_MAINNET.upper():
                logger.debug(
                    f"Mainnet: Token contract {token_address} does not match USDT contract {USDT_CONTRACT_MAINNET}"
                )
                return False

        amount_in_usdt = await extract_tronscan_amount(transaction, decimals=6)
        if amount_in_usdt is None:
            return False

        payment_amount_decimal = Decimal(str(payment_amount)).quantize(Decimal("0.000001"))
        usdt_amount_decimal = Decimal(str(amount_in_usdt)).quantize(Decimal("0.000001"))

        logger.debug(
            "USDT validation: payment_amount=%s, usdt_amount=%s, diff=%s",
            payment_amount_decimal,
            usdt_amount_decimal,
            abs(payment_amount_decimal - usdt_amount_decimal),
        )

        return abs(payment_amount_decimal - usdt_amount_decimal) <= Decimal("0.000001")

    async def _expire_payment(self, payment, settings):
        await expire_priced_payment(payment, settings, notice=NOTICE)
