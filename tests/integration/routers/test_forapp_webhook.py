"""ForApp webhook over real HTTP: auth, routing, background match, idempotency.

Uses a bare FastAPI app with only the ForApp router plus a SQLite database,
so the whole phone -> webhook -> credit path is exercised through HTTP.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import BigInteger, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import NullPool

import config
from app.db.crud import bank_deposits, transactions
from app.db.models.bank_deposit import BankDeposit
from app.db.models.transaction import Transaction
from app.db.models.user import User
from app.routers.webhook import forapp as forapp_router_module
from app.services.payments import forapp_match

USER = 9101
API_KEY = "test-key-1"

REAL_PAYLOAD = {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "test": False,
    "sender": "98500012",
    "bank": "ملت",
    "body": "بانک ملت\nواریز:2,000,210\nمانده:15,200,000",
    "amount": 2_000_210,
    "code": "210",
    "unit": "rial",
    "is_deposit": True,
    "received_at": "2026-10-10T12:00:00+03:30",
    "received_at_ms": 1791234567890,
    "attempt": 1,
    "device": "samsung SM-A546B",
}


@compiles(BigInteger, "sqlite")
def _sqlite_bigint(type_, compiler, **kw) -> str:
    return "INTEGER"


def _async(value):
    async def inner(*_, **__):
        return value

    return inner


@pytest.fixture
def setup(monkeypatch: pytest.MonkeyPatch, tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'forapp_http.db'}", poolclass=NullPool)

    async def init():
        async with engine.begin() as conn:
            await conn.run_sync(
                BankDeposit.metadata.create_all,
                tables=[BankDeposit.__table__, Transaction.__table__, User.__table__],
            )
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as session:
            session.add(User(id=USER, amount=0))
            await session.commit()
        return maker

    maker = asyncio.run(init())
    monkeypatch.setattr(transactions, "Session", maker)
    monkeypatch.setattr(bank_deposits, "Session", maker)
    settings = SimpleNamespace(
        manual_bonus_enabled=False,
        manual_bonus_percent=0,
        forapp_ttl_minutes=30,
    )
    monkeypatch.setattr(
        transactions, "SettingsManager", lambda: SimpleNamespace(get_settings=_async(settings))
    )
    monkeypatch.setattr(forapp_match, "_settings_snapshot", _async(settings))
    monkeypatch.setattr(forapp_match, "send_log_message", _async(None))
    monkeypatch.setattr(forapp_match, "try_fulfill_after_manual_credit", _async(False))
    monkeypatch.setattr(
        forapp_match, "Kenzo", SimpleNamespace(send_message=_async(None), edit_message=_async(None))
    )
    monkeypatch.setattr(config, "FORAPP_API_KEYS", API_KEY)
    monkeypatch.setattr(config, "FORAPP_API_KEY", "")
    forapp_router_module._rate_hits.clear()

    app = FastAPI()
    app.include_router(forapp_router_module.router)
    return SimpleNamespace(maker=maker, client=TestClient(app))


def _deposit_status(deposit_id: str):
    async def inner():
        async with transactions.Session() as session:
            return (
                await session.execute(select(BankDeposit.status).where(BankDeposit.id == deposit_id))
            ).scalar_one_or_none()

    return asyncio.run(inner())


def _balance() -> int:
    async def inner():
        async with transactions.Session() as session:
            return int((await session.execute(select(User.amount).where(User.id == USER))).scalar_one())

    return asyncio.run(inner())


def test_health_reports_configured(setup) -> None:
    assert setup.client.get("/payments/forapp/health").json() == {"ok": True, "configured": True}


def test_missing_and_wrong_keys_rejected(setup) -> None:
    assert setup.client.post("/payments/forapp/webhook", json=REAL_PAYLOAD).status_code == 403
    assert (
        setup.client.post(
            "/payments/forapp/webhook", json=REAL_PAYLOAD, headers={"X-API-Key": "nope"}
        ).status_code
        == 403
    )


def test_query_param_key_accepted(setup) -> None:
    payload = dict(REAL_PAYLOAD, id="qparam-1")
    response = setup.client.post("/payments/forapp/webhook?key=" + API_KEY, json=payload)
    assert response.status_code == 200
    assert response.json() == {"ok": True, "message": "unmatched"}
    assert _deposit_status("qparam-1") == "unmatched"


def test_real_sms_end_to_end_credits_user(setup) -> None:
    async def make_tx():
        return await transactions.TransactionCRUD().create(
            user_id=USER, amount=200_000, method="manual", payable_amount=200_021, amount_offset=21
        )

    tx = asyncio.run(make_tx())
    response = setup.client.post(
        "/payments/forapp/webhook", json=REAL_PAYLOAD, headers={"X-API-Key": API_KEY}
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True, "message": "matched"}
    assert _deposit_status(REAL_PAYLOAD["id"]) == "matched"
    assert _balance() == 200_021  # exact transferred sum, not the base amount

    stored = asyncio.run(transactions.TransactionCRUD().get(int(tx.id)))
    assert stored.status == "approved"

    # Phone retry with the same id replays idempotently without double credit.
    again = setup.client.post(
        "/payments/forapp/webhook", json=REAL_PAYLOAD, headers={"X-API-Key": API_KEY}
    )
    assert again.json() == {"ok": True, "message": "matched"}
    assert _balance() == 200_021


def test_idempotency_key_header_used_without_body_id(setup) -> None:
    payload = {k: v for k, v in REAL_PAYLOAD.items() if k != "id"}
    payload["amount"] = 9_999_990
    response = setup.client.post(
        "/payments/forapp/webhook",
        json=payload,
        headers={"X-API-Key": API_KEY, "Idempotency-Key": "hdr-only-1"},
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True, "message": "unmatched"}
    assert _deposit_status("hdr-only-1") == "unmatched"


def test_rate_limit_kicks_in(setup, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(forapp_router_module, "_RATE_LIMIT_MAX", 2)
    headers = {"X-API-Key": API_KEY}
    assert setup.client.post("/payments/forapp/webhook", json={"id": "rl-1"}, headers=headers).status_code == 200
    assert setup.client.post("/payments/forapp/webhook", json={"id": "rl-2"}, headers=headers).status_code == 200
    assert setup.client.post("/payments/forapp/webhook", json={"id": "rl-3"}, headers=headers).status_code == 429
