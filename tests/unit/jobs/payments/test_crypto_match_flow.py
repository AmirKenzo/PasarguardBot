"""Shared on-chain match loop and the per-chain amount tolerance it relies on."""

from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.jobs.payments import pol, ton, trx, usdt, usdt_networks
from app.jobs.payments.crypto_common import match_transfers

WALLET = "WALLET-ADDRESS"
USDT_TRC20 = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
log = logging.getLogger("test.crypto_match_flow")


def _payment(order_id: int, amount: str = "12.5") -> SimpleNamespace:
    return SimpleNamespace(order_id=order_id, amount=amount)


async def _accept_all(payment, tx: dict) -> bool:
    return True


def _run(payments, txs, consumed=None, *, fail_on=(), retry_after_error=False):
    confirmed: list[tuple[int, str]] = []

    async def confirm(payment, tx: dict, txid: str) -> None:
        if txid in fail_on:
            raise RuntimeError("db down")
        confirmed.append((payment.order_id, txid))

    matched = asyncio.run(
        match_transfers(
            payments,
            lambda payment: iter(txs),
            set() if consumed is None else consumed,
            tx_id=lambda tx: tx.get("hash"),
            accepts=_accept_all,
            confirm=confirm,
            name="TEST",
            error_message="Error processing TEST %s: %s",
            log=log,
            retry_after_error=retry_after_error,
        )
    )
    return matched, confirmed


def test_one_transfer_pays_one_invoice_only() -> None:
    matched, confirmed = _run([_payment(1), _payment(2)], [{"hash": "a"}])
    assert matched == {1}
    assert confirmed == [(1, "a")]


def test_consumed_transfer_is_skipped() -> None:
    matched, confirmed = _run([_payment(1)], [{"hash": "a"}, {"hash": "b"}], consumed={"a"})
    assert matched == {1}
    assert confirmed == [(1, "b")]


def test_transfer_without_id_is_never_credited() -> None:
    matched, confirmed = _run([_payment(1)], [{"hash": None}])
    assert matched == set()
    assert confirmed == []


@pytest.mark.parametrize(("retry", "expected"), [(False, []), (True, [(1, "b")])])
def test_confirm_error_is_logged_and_retry_is_per_chain(retry: bool, expected: list) -> None:
    matched, confirmed = _run([_payment(1)], [{"hash": "a"}, {"hash": "b"}], fail_on={"a"}, retry_after_error=retry)
    assert matched == {1}
    assert confirmed == expected


def test_confirm_error_does_not_stop_later_invoices() -> None:
    matched, confirmed = _run([_payment(1), _payment(2)], [{"hash": "a"}, {"hash": "b"}], fail_on={"a"})
    assert matched == {1, 2}
    assert confirmed == [(2, "b")]


def _trx(units: int) -> bool:
    tx = {"amount": str(units), "contractType": 1, "contractRet": "SUCCESS", "tokenInfo": {"tokenId": "_"}}
    return asyncio.run(trx.TRXProcessor()._validate_transaction(tx, "12.5", WALLET))


def _usdt_trc20(units: int) -> bool:
    tx = {"amount": str(units), "tokenInfo": {"address": USDT_TRC20}}
    return asyncio.run(usdt.USDTProcessor()._validate_transaction(tx, "12.5", WALLET))


def _ton(nano: int) -> bool:
    tx = {"in_msg": {"value": str(nano)}}
    return asyncio.run(ton.TONProcessor()._validate_transaction(tx, "12.5", WALLET))


def _pol(value: str) -> bool:
    return asyncio.run(pol._amount_matches(_payment(1), {"value": value}))


def _usdt_ton(units: int) -> bool:
    return asyncio.run(usdt_networks._ton_amount_matches(_payment(1), (str(units), {})))


def _usdt_bep20(amount: str) -> bool:
    tx = {"to": WALLET, "contractAddress": usdt_networks.BEP20_CONTRACT, "amount": Decimal(amount)}
    return usdt_networks._validate_bep20_tx(tx, "12.5", WALLET)


@pytest.mark.parametrize(
    ("check", "exact", "within", "outside"),
    [
        (_trx, 12_500_000, 12_500_001, 12_500_002),
        (_usdt_trc20, 12_500_000, 12_500_001, 12_500_002),
        (_pol, "12.5", "12.500001", "12.500002"),
        (_usdt_ton, 12_500_000, 12_500_001, 12_500_002),
        (_usdt_bep20, "12.5", "12.500001", "12.500002"),
        (_ton, 12_500_000_000, 12_500_000_000, 12_500_000_001),
    ],
    ids=["TRX", "USDT-TRC20", "POL", "USDT-TON", "USDT-BEP20", "TON"],
)
def test_amount_tolerance_per_chain(monkeypatch: pytest.MonkeyPatch, check, exact, within, outside) -> None:
    monkeypatch.setattr(usdt, "TRX_TESTNET_MODE", None)
    assert check(exact)
    assert check(within)
    assert not check(outside)
