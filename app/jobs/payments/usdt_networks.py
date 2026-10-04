"""
USDT-TON and USDT-BEP20 Payment Processor

USDT-TON uses TonAPI jetton history (TonConsole key optional);
USDT-BEP20 uses one MegaNode (NodeReal) nr_getAssetTransfers call (key required).
"""

from __future__ import annotations

from decimal import Decimal

import httpx

from app.db.crud.cryptopayments import CryptoPaymentsCRUD
from app.db.crud.settings import SettingsManager
from app.db.crud.wallets import WalletCRUD
from app.logger import get_logger
from config import TON_TESTNET_MODE

from .base import BasePaymentProcessor
from .crypto_common import amount_matches, confirm_payment, expire_payment, is_expired
from .tx_id import chain_tx_id

logger = get_logger(__name__)

NETWORK_TON = "USDT-TON"
NETWORK_BEP20 = "USDT-BEP20"
TON_JETTON_MASTER = "EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs"
BEP20_CONTRACT = "0x55d398326f99059fF775485246999027B3197955"
USDT_DECIMALS = 6
BEP20_DECIMALS = 18  # Binance-Peg USDT on BSC
NODEREAL_BSC_RPC = "https://bsc-mainnet.nodereal.io/v1/{api_key}"
UNIT = "USDT"


def _price_line(settings) -> str:
    return f"<b>📊 قیمت دلار:</b> <code>{settings.arz_usd:,}</code> هزارتومان"


def _parse_hex_or_int(value) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return 0
    return int(text, 16) if text.startswith("0x") else int(text)


# ---------------------------------------------------------------------------
# TON (Jetton)
# ---------------------------------------------------------------------------


def _tonapi_base_url() -> str:
    return "https://testnet.tonapi.io" if TON_TESTNET_MODE == "testnet" else "https://tonapi.io"


async def _fetch_ton_usdt_events(client, headers, address_wallet, start_time) -> list[dict]:
    url = f"{_tonapi_base_url()}/v2/accounts/{address_wallet}/jettons/{TON_JETTON_MASTER}/history"
    params = {"limit": 100}
    if start_time:
        params["start_date"] = int(start_time)
    try:
        response = await client.get(url, headers=headers, params=params, timeout=30.0)
        if response.status_code != 200:
            logger.error("TonAPI USDT history failed: %s", response.status_code)
            return []
        data = response.json()
        return data.get("events") or data.get("operations") or []
    except Exception as e:
        logger.error("Failed TonAPI USDT history: %s", e)
        return []


def _iter_ton_incoming(event, account_raw: str | None):
    if not isinstance(event, dict):
        return
    target = account_raw or (event.get("account") or {}).get("address")
    for action in event.get("actions") or []:
        if action.get("type") != "JettonTransfer":
            continue
        if str(action.get("status") or "").lower() == "failed":
            continue
        transfer = action.get("JettonTransfer") or {}
        recipient = transfer.get("recipient") or {}
        recipient_addr = recipient.get("address") if isinstance(recipient, dict) else recipient
        if target and recipient_addr and recipient_addr != target:
            continue
        amount = transfer.get("amount")
        if not amount:
            continue
        tx_hash = event.get("event_id") or "N/A"
        base_txs = action.get("base_transactions") or []
        if base_txs:
            tx_hash = base_txs[-1]
        sender = transfer.get("sender")
        yield (
            amount,
            {
                "hash": tx_hash,
                "from": sender.get("address") if isinstance(sender, dict) else "N/A",
                "to": recipient_addr or target or "N/A",
                "timestamp": event.get("timestamp") or 0,
                "block": event.get("lt") or "N/A",
                "confirmed": not event.get("in_progress", False),
                "explorer_html": (
                    f"<b>🔗 مشاهده:</b> <a href='https://tonviewer.com/transaction/{tx_hash}'>لینک تراکنش</a>"
                    if tx_hash != "N/A"
                    else ""
                ),
            },
        )


# ---------------------------------------------------------------------------
# BEP20 (BSC) — MegaNode (NodeReal) only, one RPC per check
# ---------------------------------------------------------------------------


async def _fetch_bep20_transfers(client, address_wallet, api_key, start_time) -> list[dict]:
    rpc_url = NODEREAL_BSC_RPC.format(api_key=api_key.strip())
    try:
        response = await client.post(
            rpc_url,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "nr_getAssetTransfers",
                "params": [
                    {
                        "category": ["20"],
                        "contractAddresses": [BEP20_CONTRACT],
                        "toAddress": address_wallet,
                        "order": "desc",
                        "excludeZeroValue": True,
                        "maxCount": "0x64",
                    }
                ],
            },
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("error"):
            raise RuntimeError(data["error"])
        result = data.get("result")
        transfers = result.get("transfers") if isinstance(result, dict) else result
        if not isinstance(transfers, list):
            return []

        out = []
        for item in transfers:
            ts = _parse_hex_or_int(item.get("blockTimeStamp") or item.get("timestamp") or 0)
            if ts and ts < int(start_time):
                continue
            decimals = _parse_hex_or_int(item.get("decimal") or BEP20_DECIMALS)
            if decimals <= 0:
                decimals = BEP20_DECIMALS
            tx_hash = item.get("hash") or "N/A"
            out.append(
                {
                    "hash": tx_hash,
                    "from": item.get("from") or "N/A",
                    "to": item.get("to") or address_wallet,
                    "contractAddress": item.get("contractAddress") or BEP20_CONTRACT,
                    "amount": Decimal(_parse_hex_or_int(item.get("value") or 0)) / (Decimal(10) ** decimals),
                    "timestamp": ts or int(start_time),
                    "block": str(_parse_hex_or_int(item.get("blockNum") or item.get("blockNumber") or 0)),
                    "confirmed": True,
                    "explorer_html": (
                        f"<b>🔗 مشاهده در BscScan:</b> <a href='https://bscscan.com/tx/{tx_hash}'>لینک تراکنش</a>"
                        if tx_hash != "N/A"
                        else ""
                    ),
                }
            )
        logger.info("USDT-BEP20 via MegaNode: %s tx(s)", len(out))
        return out
    except Exception as e:
        logger.error("Failed USDT-BEP20 MegaNode fetch: %s", e)
        return []


def _validate_bep20_tx(tx: dict, payment_amount, address_wallet: str) -> bool:
    if (tx.get("to") or "").lower() != address_wallet.lower():
        return False
    if (tx.get("contractAddress") or "").lower() != BEP20_CONTRACT.lower():
        return False
    return amount_matches(payment_amount, tx["amount"])


# ---------------------------------------------------------------------------
# Processor
# ---------------------------------------------------------------------------


class USDTNetworksProcessor(BasePaymentProcessor):
    def __init__(self):
        super().__init__("usdt_networks")

    async def check_payments(self):
        settings = await SettingsManager().get_settings()
        async with httpx.AsyncClient(timeout=30.0) as client:
            for checker in (self._check_ton, self._check_bep20):
                try:
                    await checker(client, settings)
                except Exception:
                    logger.exception("USDT checker %s failed", checker.__name__)

    async def _pending_valid(self, network: str, settings) -> list:
        valid = []
        for payment in await CryptoPaymentsCRUD().get_pending_by_arz(network):
            if is_expired(payment):
                await expire_payment(payment, unit=UNIT, price_line=_price_line(settings))
            else:
                valid.append(payment)
        return valid

    async def _check_ton(self, client, settings):
        valid = await self._pending_valid(NETWORK_TON, settings)
        if not valid:
            return
        wallet = await WalletCRUD().get_wallet_by_type(NETWORK_TON)
        if not wallet:
            logger.debug("USDT-TON wallet not configured — skipping")
            return

        api_key = (wallet.api_key or "").strip()
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        earliest = min(int(p.createtime) for p in valid)
        events = await _fetch_ton_usdt_events(client, headers, wallet.address, earliest)
        account_raw = (events[0].get("account") or {}).get("address") if events else None
        consumed: set[str] = set()

        for payment in valid:
            matched = False
            for event in events:
                event_ts = event.get("timestamp") or event.get("utime") or 0
                if event_ts and int(event_ts) < int(payment.createtime):
                    continue
                for amount_units, tx_details in _iter_ton_incoming(event, account_raw):
                    txid = chain_tx_id(tx_details)
                    if txid and txid in consumed:
                        continue
                    received = Decimal(str(amount_units)) / (Decimal(10) ** USDT_DECIMALS)
                    if not amount_matches(payment.amount, received):
                        continue
                    if txid:
                        consumed.add(txid)
                    try:
                        await confirm_payment(
                            payment, settings, tx_details, unit=UNIT, price_line=_price_line(settings)
                        )
                    except Exception as e:
                        logger.error("Error processing USDT-TON %s: %s", payment.order_id, e)
                    matched = True
                    break
                if matched:
                    break

    async def _check_bep20(self, client, settings):
        valid = await self._pending_valid(NETWORK_BEP20, settings)
        if not valid:
            return
        wallet = await WalletCRUD().get_wallet_by_type(NETWORK_BEP20)
        if not wallet:
            logger.debug("USDT-BEP20 wallet not configured — skipping")
            return
        api_key = (wallet.api_key or "").strip()
        if not api_key:
            logger.warning("USDT-BEP20 MegaNode API key missing — skipping")
            return

        earliest = min(int(p.createtime) for p in valid)
        txs = await _fetch_bep20_transfers(client, wallet.address, api_key, earliest)
        consumed: set[str] = set()
        for payment in valid:
            for tx in txs:
                if int(tx.get("timestamp") or 0) < int(payment.createtime):
                    continue
                txid = chain_tx_id(tx)
                if txid and txid in consumed:
                    continue
                if not _validate_bep20_tx(tx, payment.amount, wallet.address):
                    continue
                if txid:
                    consumed.add(txid)
                try:
                    await confirm_payment(payment, settings, tx, unit=UNIT, price_line=_price_line(settings))
                except Exception as e:
                    logger.error("Error processing USDT-BEP20 %s: %s", payment.order_id, e)
                break
