"""Crypto invoice jobs match transactions before expiring, honor the expiry grace and credit once.

One on-chain transfer pays at most one invoice: its id is stored on the invoice (unique), skipped by
a pre-check on later runs, and a second credit attempt hits the unique index and is refused.

Every on-chain processor runs against a fake explorer (httpx.MockTransport) and a real SQLite
database, so the whole run (fetch -> match -> credit -> expire) is exercised per network.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import BigInteger, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import NullPool

from app.db.crud import cryptopayments
from app.db.models.cryptopayments import CryptoPayments
from app.db.models.user import User
from app.jobs.payments import crypto_common, pol, ton, trx, usdt, usdt_networks

USER = 3003
ORDER = 777001
AMOUNT_IRT = 100_000
WALLET = "WALLET-ADDRESS"
MINUTE = 60
USDT_TRC20_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"


@compiles(BigInteger, "sqlite")
def _sqlite_bigint(type_, compiler, **kw) -> str:
    return "INTEGER"


def _async(value):
    async def inner(*_, **__):
        return value

    return inner


@dataclass(frozen=True)
class Network:
    arz: str
    amount: str
    run: Callable[[], object]
    response: Callable[[str, int], dict]


def _trx_response(tx_hash: str, ts: int) -> dict:
    tx = {
        "hash": tx_hash,
        "timestamp": ts * 1000,
        "to": WALLET,
        "amount": "12500000",
        "contractType": 1,
        "contractRet": "SUCCESS",
        "tokenInfo": {"tokenId": "_"},
    }
    return {"data": [tx]}


def _usdt_trc20_response(tx_hash: str, ts: int) -> dict:
    tx = {
        "hash": tx_hash,
        "timestamp": ts * 1000,
        "to": WALLET,
        "amount": "12500000",
        "tokenInfo": {"address": USDT_TRC20_CONTRACT},
    }
    return {"data": [tx]}


def _ton_response(tx_hash: str, ts: int) -> dict:
    tx = {"transaction_id": {"hash": tx_hash}, "utime": ts, "in_msg": {"value": "12500000000", "destination": WALLET}}
    return {"ok": True, "result": [tx]}


def _pol_response(tx_hash: str, ts: int) -> dict:
    block_ts = datetime.fromtimestamp(ts, tz=UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    transfer = {"hash": tx_hash, "to": WALLET, "value": 12.5, "metadata": {"blockTimestamp": block_ts}}
    return {"jsonrpc": "2.0", "id": 1, "result": {"transfers": [transfer]}}


def _usdt_ton_response(tx_hash: str, ts: int) -> dict:
    action = {
        "type": "JettonTransfer",
        "status": "ok",
        "JettonTransfer": {"amount": "12500000", "recipient": {"address": WALLET}, "sender": {"address": "SENDER"}},
    }
    return {"events": [{"event_id": tx_hash, "timestamp": ts, "account": {"address": WALLET}, "actions": [action]}]}


def _usdt_bep20_response(tx_hash: str, ts: int) -> dict:
    transfer = {
        "hash": tx_hash,
        "to": WALLET,
        "contractAddress": usdt_networks.BEP20_CONTRACT,
        "value": hex(int(Decimal("12.5") * 10**18)),
        "blockTimeStamp": ts,
    }
    return {"jsonrpc": "2.0", "id": 1, "result": {"transfers": [transfer]}}


NETWORKS = {
    "TRX": Network("TRX", "12.5", lambda: trx.TRXProcessor().check_payments(), _trx_response),
    "USDT": Network("USDT", "12.5", lambda: usdt.USDTProcessor().check_payments(), _usdt_trc20_response),
    "TON": Network("TON", "12.5", lambda: ton.TONProcessor().check_payments(), _ton_response),
    "POL": Network("POL", "12.5", lambda: pol.POLProcessor().check_payments(), _pol_response),
    "USDT-TON": Network(
        "USDT-TON", "12.5", lambda: usdt_networks.USDTNetworksProcessor().check_payments(), _usdt_ton_response
    ),
    "USDT-BEP20": Network(
        "USDT-BEP20", "12.5", lambda: usdt_networks.USDTNetworksProcessor().check_payments(), _usdt_bep20_response
    ),
}


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        crypto_bonus_enabled=False,
        crypto_bonus_percent=0,
        arz_trx=10,
        arz_usd=100,
        arz_ton=200,
        arz_pol=30,
    )


class Explorer:
    """Serves at most one incoming transfer; ``tx`` is ``(hash, unix_seconds)`` or ``None``."""

    def __init__(self, network: Network) -> None:
        self.network = network
        self.tx: tuple[str, int] | None = None

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.tx is None:
            empty = {"data": [], "ok": True, "result": {"transfers": []}, "events": []}
            if self.network.arz == "TON":
                empty["result"] = []
            return httpx.Response(200, json=empty)
        return httpx.Response(200, json=self.network.response(*self.tx))


@pytest.fixture(params=list(NETWORKS))
def env(request, monkeypatch: pytest.MonkeyPatch, tmp_path) -> SimpleNamespace:
    network = NETWORKS[request.param]
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'grace.db'}", poolclass=NullPool)

    async def setup():
        async with engine.begin() as conn:
            await conn.run_sync(CryptoPayments.metadata.create_all, tables=[CryptoPayments.__table__, User.__table__])
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as session:
            session.add(User(id=USER, amount=0))
            await session.commit()
        return maker

    monkeypatch.setattr(cryptopayments, "Session", asyncio.run(setup()))

    explorer = Explorer(network)
    transport = httpx.MockTransport(explorer.handler)
    real_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda *a, **kw: real_client(*a, transport=transport, **kw))

    wallet = SimpleNamespace(address=WALLET, api_key="test-key")
    settings_manager = SimpleNamespace(get_settings=_async(_settings()))
    sent: list[tuple[int, str]] = []

    async def send_message(user_id, text, **_):
        sent.append((user_id, text))

    bot = SimpleNamespace(send_message=send_message, delete_messages=_async(None))
    for module in (trx, usdt, ton, pol, usdt_networks):
        monkeypatch.setattr(module, "SettingsManager", lambda: settings_manager)
        monkeypatch.setattr(module, "WalletCRUD", lambda: SimpleNamespace(get_wallet_by_type=_async(wallet)))
    for module in (trx, usdt, ton, crypto_common):
        monkeypatch.setattr(module, "Kenzo", bot)
        monkeypatch.setattr(module, "send_log_message", _async(None))
        monkeypatch.setattr(module, "try_fulfill_after_crypto_credit", _async(False))
        monkeypatch.setattr(module, "cancel_after_crypto_expire", _async(None))
        monkeypatch.setattr(module, "calculate_payment_bonus", _async(0))
    for module in (usdt, trx):
        monkeypatch.setattr(module, "TRX_TESTNET_MODE", None)
    monkeypatch.setattr(ton, "TON_TESTNET_MODE", None)
    monkeypatch.setattr(usdt_networks, "TON_TESTNET_MODE", None)

    return SimpleNamespace(network=network, explorer=explorer, sent=sent)


async def _create_invoice(env: SimpleNamespace, age_seconds: int) -> int:
    createtime = int(time.time()) - age_seconds
    result = await cryptopayments.add_order_crypto_payment(
        order_id=ORDER,
        user_id=USER,
        arz=env.network.arz,
        amount=env.network.amount,
        amount_irt=AMOUNT_IRT,
        createtime=createtime,
    )
    assert result["success"] is True
    return createtime


async def _age_invoice(age_seconds: int) -> None:
    async with cryptopayments.Session() as session, session.begin():
        await session.execute(
            update(CryptoPayments)
            .where(CryptoPayments.order_id == ORDER)
            .values(createtime=int(time.time()) - age_seconds)
        )


async def _state() -> tuple[str, int]:
    async with cryptopayments.Session() as session:
        status = (await session.execute(select(CryptoPayments.status).where(CryptoPayments.order_id == ORDER))).scalar()
        balance = (await session.execute(select(User.amount).where(User.id == USER))).scalar()
    return str(status), int(balance or 0)


def test_tx_at_minute_29_seen_at_minute_31_is_credited(env: SimpleNamespace) -> None:
    async def scenario():
        createtime = await _create_invoice(env, 31 * MINUTE)
        env.explorer.tx = ("hash-late", createtime + 29 * MINUTE)
        await env.network.run()
        return await _state()

    assert asyncio.run(scenario()) == ("Paid", AMOUNT_IRT)


def test_tx_after_ttl_and_tolerance_is_ignored_and_invoice_expires_after_grace(env: SimpleNamespace) -> None:
    async def scenario():
        createtime = await _create_invoice(env, 35 * MINUTE)
        too_late = createtime + crypto_common.INVOICE_TTL_SECONDS + crypto_common.TX_TIME_TOLERANCE_SECONDS + 1
        env.explorer.tx = ("hash-too-late", too_late)
        await env.network.run()
        within_grace = await _state()
        await _age_invoice(41 * MINUTE)
        await env.network.run()
        return within_grace, await _state()

    within_grace, after_grace = asyncio.run(scenario())
    assert within_grace == ("Pending", 0)
    assert after_grace == ("Expired", 0)


def test_unmatched_invoice_stays_pending_in_grace_then_expires(env: SimpleNamespace) -> None:
    async def scenario():
        await _create_invoice(env, 35 * MINUTE)
        await env.network.run()
        at_35 = await _state()
        sent_at_35 = len(env.sent)
        await _age_invoice(41 * MINUTE)
        await env.network.run()
        return at_35, sent_at_35, await _state(), len(env.sent)

    at_35, sent_at_35, at_41, sent_at_41 = asyncio.run(scenario())
    assert at_35 == ("Pending", 0)
    assert sent_at_35 == 0
    assert at_41 == ("Expired", 0)
    assert sent_at_41 == 1  # one expiry notice to the user


def test_same_tx_in_two_runs_is_credited_once(env: SimpleNamespace) -> None:
    async def scenario():
        createtime = await _create_invoice(env, 5 * MINUTE)
        env.explorer.tx = ("hash-once", createtime + 2 * MINUTE)
        await env.network.run()
        await env.network.run()
        await _age_invoice(41 * MINUTE)
        await env.network.run()
        return await _state(), len(env.sent)

    state, sent = asyncio.run(scenario())
    assert state == ("Paid", AMOUNT_IRT)
    assert sent == 1  # one payment notice, no expiry notice for a paid invoice


def test_crud_credit_and_expire_are_conditional_on_pending(env: SimpleNamespace) -> None:
    async def scenario():
        await _create_invoice(env, 0)
        crud = cryptopayments.CryptoPaymentsCRUD()
        first = await crud.approve_and_credit(ORDER, AMOUNT_IRT, int(time.time()))
        second = await crud.approve_and_credit(ORDER, AMOUNT_IRT, int(time.time()))
        expired = await crud.expire_payment(ORDER)
        return first, second, expired, await _state()

    first, second, expired, state = asyncio.run(scenario())
    assert first is not None and first[1] == AMOUNT_IRT
    assert second is None
    assert expired is False
    assert state == ("Paid", AMOUNT_IRT)


SECOND_ORDER = ORDER + 1
OTHER_ORDER = ORDER + 2


async def _add_invoice(env: SimpleNamespace, order_id: int, createtime: int) -> None:
    result = await cryptopayments.add_order_crypto_payment(
        order_id=order_id,
        user_id=USER,
        arz=env.network.arz,
        amount=env.network.amount,
        amount_irt=AMOUNT_IRT,
        createtime=createtime,
    )
    assert result["success"] is True


async def _add_paid_with_hash(env: SimpleNamespace, tx_hash: str) -> None:
    await _add_invoice(env, OTHER_ORDER, int(time.time()) - 60 * MINUTE)
    async with cryptopayments.Session() as session, session.begin():
        await session.execute(
            update(CryptoPayments).where(CryptoPayments.order_id == OTHER_ORDER).values(status="Paid", tx_hash=tx_hash)
        )


async def _rows() -> dict[int, tuple[str, str | None]]:
    async with cryptopayments.Session() as session:
        result = await session.execute(select(CryptoPayments.order_id, CryptoPayments.status, CryptoPayments.tx_hash))
        return {int(order_id): (str(status), tx_hash) for order_id, status, tx_hash in result.all()}


async def _balance() -> int:
    async with cryptopayments.Session() as session:
        return int((await session.execute(select(User.amount).where(User.id == USER))).scalar() or 0)


def test_one_tx_matching_two_same_amount_invoices_credits_exactly_one(env: SimpleNamespace) -> None:
    async def scenario():
        createtime = int(time.time()) - 5 * MINUTE
        await _add_invoice(env, ORDER, createtime)
        await _add_invoice(env, SECOND_ORDER, createtime)
        env.explorer.tx = ("hash-shared", createtime + 2 * MINUTE)
        await env.network.run()
        await env.network.run()
        return await _rows(), await _balance()

    rows, balance = asyncio.run(scenario())
    statuses = sorted(status for status, _ in rows.values())
    assert statuses == ["Paid", "Pending"]
    assert [h for status, h in rows.values() if status == "Paid"] == ["hash-shared"]
    assert balance == AMOUNT_IRT


def test_tx_already_stored_is_skipped_before_crediting(env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    attempts: list[int] = []
    real_credit = cryptopayments.CryptoPaymentsCRUD.approve_and_credit

    async def spy(self, order_id, *args, **kwargs):
        attempts.append(int(order_id))
        return await real_credit(self, order_id, *args, **kwargs)

    monkeypatch.setattr(cryptopayments.CryptoPaymentsCRUD, "approve_and_credit", spy)

    async def scenario():
        await _add_paid_with_hash(env, "hash-used")
        createtime = await _create_invoice(env, 5 * MINUTE)
        env.explorer.tx = ("hash-used", createtime + 2 * MINUTE)
        await env.network.run()
        return await _state()

    assert asyncio.run(scenario()) == ("Pending", 0)
    assert attempts == []


def test_unique_index_refuses_second_credit_when_precheck_misses(
    env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cryptopayments.CryptoPaymentsCRUD, "get_used_tx_hashes", _async(set()))

    async def scenario():
        await _add_paid_with_hash(env, "hash-raced")
        createtime = await _create_invoice(env, 5 * MINUTE)
        env.explorer.tx = ("hash-raced", createtime + 2 * MINUTE)
        await env.network.run()
        return await _state(), len(env.sent)

    state, sent = asyncio.run(scenario())
    assert state == ("Pending", 0)
    assert sent == 0
