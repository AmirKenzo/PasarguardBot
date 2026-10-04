"""
POL Payment Processor

Confirms native POL (Polygon) deposits with one Alchemy alchemy_getAssetTransfers call (key required).
"""

from __future__ import annotations

from datetime import datetime

import httpx

from app.db.crud.cryptopayments import CryptoPaymentsCRUD
from app.db.crud.settings import SettingsManager
from app.db.crud.wallets import WalletCRUD
from app.logger import get_logger

from .base import BasePaymentProcessor
from .crypto_common import amount_matches, confirm_payment, expire_payment, is_expired
from .tx_id import chain_tx_id

logger = get_logger(__name__)

NETWORK = "POL"
ALCHEMY_POLYGON_RPC = "https://polygon-mainnet.g.alchemy.com/v2/{api_key}"


def _price_line(settings) -> str:
    return f"<b>📊 قیمت POL:</b> <code>{settings.arz_pol:,}</code> هزارتومان"


def _parse_transfer_timestamp(item: dict) -> int:
    block_ts = (item.get("metadata") or {}).get("blockTimestamp")
    if isinstance(block_ts, str) and block_ts:
        try:
            return int(datetime.fromisoformat(block_ts.replace("Z", "+00:00")).timestamp())
        except ValueError:
            pass
    return int(item.get("timestamp") or 0)


def _tx_details(item: dict, address_wallet: str) -> dict:
    tx_hash = item.get("hash") or "N/A"
    return {
        "hash": tx_hash,
        "from": item.get("from") or "N/A",
        "to": item.get("to") or address_wallet,
        "timestamp": _parse_transfer_timestamp(item),
        "block": item.get("blockNum") or item.get("blockNumber") or "N/A",
        "confirmed": True,
        "explorer_html": (
            f"<b>🔗 مشاهده در Polygonscan:</b> <a href='https://polygonscan.com/tx/{tx_hash}'>لینک تراکنش</a>"
            if tx_hash != "N/A"
            else ""
        ),
    }


async def _fetch_pol_transfers(client, api_key: str, address_wallet: str) -> list[dict]:
    """Single alchemy_getAssetTransfers call for native POL deposits."""
    url = ALCHEMY_POLYGON_RPC.format(api_key=api_key.strip())
    try:
        response = await client.post(
            url,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "alchemy_getAssetTransfers",
                "params": [
                    {
                        "toAddress": address_wallet,
                        "category": ["external"],
                        "order": "desc",
                        "withMetadata": True,
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
        transfers = (data.get("result") or {}).get("transfers") or []
        logger.info("POL via Alchemy: %s tx(s)", len(transfers))
        return transfers if isinstance(transfers, list) else []
    except Exception as e:
        logger.error("Failed POL Alchemy fetch: %s", e)
        return []


class POLProcessor(BasePaymentProcessor):
    def __init__(self):
        super().__init__("pol")

    async def check_payments(self):
        pending = await CryptoPaymentsCRUD().get_pending_by_arz(NETWORK)
        if not pending:
            return
        settings = await SettingsManager().get_settings()

        valid = []
        for payment in pending:
            if is_expired(payment):
                await expire_payment(payment, unit="POL", price_line=_price_line(settings))
            else:
                valid.append(payment)
        if not valid:
            return

        wallet = await WalletCRUD().get_wallet_by_type(NETWORK)
        if not wallet:
            logger.debug("POL wallet not configured — skipping")
            return
        api_key = (wallet.api_key or "").strip()
        if not api_key:
            logger.warning("POL Alchemy API key missing — skipping")
            return

        address_wallet = wallet.address
        async with httpx.AsyncClient(timeout=30.0) as client:
            transfers = await _fetch_pol_transfers(client, api_key, address_wallet)
        consumed: set[str] = set()
        for payment in valid:
            for item in transfers:
                ts = _parse_transfer_timestamp(item)
                if ts and ts < int(payment.createtime):
                    continue
                if (item.get("to") or "").lower() != address_wallet.lower():
                    continue
                txid = chain_tx_id(item)
                if txid and txid in consumed:
                    continue
                try:
                    amount_pol = float(item.get("value") or 0)
                except TypeError, ValueError:
                    continue
                if amount_pol <= 0 or not amount_matches(payment.amount, amount_pol):
                    continue
                if txid:
                    consumed.add(txid)
                try:
                    await confirm_payment(
                        payment,
                        settings,
                        _tx_details(item, address_wallet),
                        unit="POL",
                        price_line=_price_line(settings),
                    )
                except Exception as e:
                    logger.error("Error processing POL %s: %s", payment.order_id, e)
                break
