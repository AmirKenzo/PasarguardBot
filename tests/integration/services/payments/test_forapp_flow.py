"""ForApp flow: reserve -> SMS webhook -> auto-credit, run against SQLite.

Covers the happy path (rial SMS matches the reserved payable exactly once),
replay idempotency, and the unmatched path. Fake Kenzo/log/fulfill so no
Telegram or network is touched.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from sqlalchemy import BigInteger, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import NullPool

from app.db.crud import bank_deposits, transactions
from app.db.models.bank_deposit import BankDeposit
from app.db.models.transaction import Transaction
from app.db.models.user import User
from app.services.payments import forapp_match

USER = 9001


@compiles(BigInteger, "sqlite")
def _sqlite_bigint(type_, compiler, **kw) -> str:
    return "INTEGER"


def _async(value):
    async def inner(*_, **__):
        return value

    return inner


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch, tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'forapp.db'}", poolclass=NullPool)

    async def setup():
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

    maker = asyncio.run(setup())
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
    sent: list[tuple[int, str]] = []

    async def _send(user_id: int, text: str, **kwargs):
        sent.append((int(user_id), text))

    monkeypatch.setattr(forapp_match, "Kenzo", SimpleNamespace(send_message=_send, edit_message=_async(None)))
    return SimpleNamespace(maker=maker, sent=sent)


async def _balance() -> int:
    async with transactions.Session() as session:
        return int((await session.execute(select(User.amount).where(User.id == USER))).scalar_one())


def test_rial_sms_matches_payable_and_credits_once(db) -> None:
    async def scenario():
        tx = await transactions.TransactionCRUD().create(
            user_id=USER, amount=200_000, method="manual", payable_amount=200_021, amount_offset=21
        )
        # Real ForApp default JSON template (Request.defaultBody).
        payload = {
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
        first = await forapp_match.process_forapp_deposit(payload)
        replay = await forapp_match.process_forapp_deposit(payload)
        stored = await transactions.TransactionCRUD().get(int(tx.id))
        return first, replay, stored, await _balance()

    first, replay, stored, balance = asyncio.run(scenario())
    assert first["status"] == "matched"
    assert replay["status"] == "matched"  # idempotent replay
    assert stored.status == "approved"
    assert balance == 200_021  # exact transferred sum (base + offset) + 0 bonus, credited once
    assert db.sent and db.sent[0][0] == USER


def test_unknown_amount_stays_unmatched(db) -> None:
    async def scenario():
        await transactions.TransactionCRUD().create(
            user_id=USER, amount=200_000, method="manual", payable_amount=200_021, amount_offset=21
        )
        result = await forapp_match.process_forapp_deposit(
            {"id": "sms-2", "raw_amount": 5_000_000, "unit": "rial", "is_deposit": True}
        )
        return result, await _balance()

    result, balance = asyncio.run(scenario())
    assert result["status"] == "unmatched"
    assert balance == 0


def test_withdrawal_sms_is_ignored(db) -> None:
    async def scenario():
        return await forapp_match.process_forapp_deposit(
            {"id": "sms-3", "amount": 2_000_210, "unit": "rial", "is_deposit": False}
        )

    result = asyncio.run(scenario())
    assert result["status"] == "ignored"


def test_approved_without_receipt_finder(db) -> None:
    import time

    from app.db.crud.transactions import TransactionCRUD

    async def scenario():
        crud = TransactionCRUD()
        now = int(time.time())
        auto = await crud.create(
            user_id=USER, amount=200_000, method="manual", payable_amount=200_021, amount_offset=21
        )
        await crud.update(auto.id, status="approved", completed_at=now)
        with_receipt = await crud.create(
            user_id=USER, amount=100_000, method="manual", payable_amount=100_005, amount_offset=5
        )
        await crud.update(with_receipt.id, status="approved", completed_at=now, message_id=11, message_chat_id=22)
        other_user = await crud.create(
            user_id=USER + 1, amount=50_000, method="manual", payable_amount=50_007, amount_offset=7
        )
        await crud.update(other_user.id, status="approved", completed_at=now)
        since = now - 24 * 60 * 60
        found = await crud.find_recent_approved_payable_without_receipt(USER, since)
        missing_user = await crud.find_recent_approved_payable_without_receipt(999999, since)
        too_old = await crud.find_recent_approved_payable_without_receipt(USER, now + 3600)
        return found, missing_user, too_old

    found, missing_user, too_old = asyncio.run(scenario())
    assert found is not None and int(found.payable_amount) == 200_021
    assert missing_user is None
    assert too_old is None


def test_app_test_button_marks_test_without_credit(db) -> None:
    async def scenario():
        result = await forapp_match.process_forapp_deposit(
            {
                "id": "test-3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "test": True,
                "sender": "ForApp",
                "bank": "آزمایشی",
                "body": "پیامک آزمایشی ForApp\nواریز: 1,000,123 ریال",
                "amount": 1_000_123,
                "code": "123",
                "unit": "rial",
                "is_deposit": True,
                "received_at_ms": 1791234567890,
                "attempt": 1,
                "device": "samsung SM-A546B",
            }
        )
        return result, await _balance()

    result, balance = asyncio.run(scenario())
    assert result["status"] == "test"
    assert balance == 0
