"""USDT-TRC20 rows from the /api/token_trc20/transfers fallback carry their time in ``block_ts`` (ms)."""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace

import httpx
import pytest

from app.jobs.payments import usdt
from app.jobs.payments.crypto_common import tx_time_in_window
from app.jobs.payments.tx_id import chain_tx_id

WALLET = "TWalletAddress"
USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"


def _trc20_row(ts_ms: int) -> dict:
    return {
        "transaction_id": "trc20-hash",
        "block_ts": ts_ms,
        "from_address": "TSender",
        "to_address": WALLET,
        "contract_address": USDT_CONTRACT,
        "quant": "12500000",
        "confirmed": True,
        "contractRet": "SUCCESS",
        "finalResult": "SUCCESS",
        "tokenInfo": {"tokenId": USDT_CONTRACT, "tokenAbbr": "USDT", "tokenDecimal": 6},
    }


def _fetch(row: dict) -> list[dict]:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/api/token_trc20/transfers"):
            return httpx.Response(200, json={"token_transfers": [row]})
        return httpx.Response(200, json={"data": []})

    async def run() -> list[dict]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await usdt._fetch_token_transfers(client, "https://tronscan.test", {}, WALLET, 0, "batch", None)

    return asyncio.run(run())


@pytest.mark.parametrize("scale", [1000, 1], ids=["ms", "seconds"])
def test_block_ts_is_read_as_unix_seconds(scale: int) -> None:
    ts = int(time.time()) - 120
    assert usdt._tx_unix_seconds({"block_ts": ts * scale}) == ts


def test_fallback_row_is_in_window_and_validates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(usdt, "TRX_TESTNET_MODE", None)
    createtime = int(time.time()) - 5 * 60
    rows = _fetch(_trc20_row((createtime + 120) * 1000))
    assert len(rows) == 1
    row = rows[0]

    payment = SimpleNamespace(createtime=createtime)
    assert tx_time_in_window(payment, usdt._tx_unix_seconds(row))
    assert chain_tx_id(row) == "trc20-hash"
    assert usdt._tx_recipient(row) == WALLET
    assert asyncio.run(usdt.USDTProcessor()._validate_transaction(row, "12.5", WALLET)) is True


def test_failed_fallback_row_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(usdt, "TRX_TESTNET_MODE", None)
    row = _trc20_row(int(time.time()) * 1000) | {"contractRet": "REVERT"}
    assert asyncio.run(usdt.USDTProcessor()._validate_transaction(row, "12.5", WALLET)) is False
