from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import BigInteger, delete, event, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import NullPool

from app.db.crud import auto_card
from app.db.models.auto_card import AutoCard
from app.db.models.transaction import Transaction
from app.db.models.user import User

USER = 42
CODE = 60001
RIAL = 1_000_123


@compiles(BigInteger, "sqlite")
def _sqlite_bigint(type_, compiler, **kw) -> str:
    return "INTEGER"


@pytest.fixture
async def db(monkeypatch, tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'payment.db'}", poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(
            AutoCard.metadata.create_all, tables=[AutoCard.__table__, User.__table__, Transaction.__table__]
        )
    sessions = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    monkeypatch.setattr(auto_card, "GetDB", sessions)
    async with sessions() as session:
        session.add(User(id=USER, amount=1000))
        session.add(AutoCard(code=CODE, id=USER, amount=RIAL, first_amount=100_000, time=1, status=False))
        await session.commit()
    yield SimpleNamespace(engine=engine, sessions=sessions)
    await engine.dispose()


async def _approve(*, bonus_enabled=True):
    return await auto_card.CRUDAutoCard().approve_and_credit(RIAL, bonus_enabled=bonus_enabled, bonus_percent=10)


async def _read(db):
    async with db.sessions() as session:
        invoice = await session.get(AutoCard, CODE)
        wallet = await session.get(User, USER)
        transactions = list((await session.scalars(select(Transaction))).all())
        return invoice.status, wallet.amount if wallet else None, transactions


def _assert_one_payment(rows):
    assert len(rows) == 1
    transaction = rows[0]
    assert (transaction.user_id, transaction.amount, transaction.method, transaction.status) == (
        USER,
        100_000,
        "auto",
        "approved",
    )
    assert transaction.created_at > 0
    assert transaction.completed_at == transaction.created_at


async def test_payment_credits_wallet_and_records_transaction_once(db):
    result = await _approve()
    assert (result.invoice.code, result.invoice.status, result.balance, result.bonus) == (CODE, True, 111_000, 10_000)
    status, balance, rows = await _read(db)
    assert (status, balance) == (True, 111_000)
    _assert_one_payment(rows)


async def test_bonus_disabled_credits_original_amount(db):
    result = await _approve(bonus_enabled=False)
    assert (result.balance, result.bonus) == (101_000, 0)
    status, balance, rows = await _read(db)
    assert (status, balance) == (True, 101_000)
    _assert_one_payment(rows)


async def test_duplicate_approval_has_no_financial_effect(db):
    await _approve()
    assert await _approve() is None
    status, balance, rows = await _read(db)
    assert (status, balance) == (True, 111_000)
    _assert_one_payment(rows)


async def test_transaction_insert_failure_rolls_back_invoice_and_credit(db):
    writes = []

    def fail_insert(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("UPDATE AUTO_CART"):
            writes.append(statement)
        if statement.lstrip().upper().startswith("INSERT INTO TRANSACTIONS"):
            raise OperationalError(statement, parameters, RuntimeError("ledger unavailable"))

    event.listen(db.engine.sync_engine, "before_cursor_execute", fail_insert)
    try:
        with pytest.raises(OperationalError):
            await _approve()
    finally:
        event.remove(db.engine.sync_engine, "before_cursor_execute", fail_insert)
    assert writes
    status, balance, rows = await _read(db)
    assert (status, balance, rows) == (False, 1000, [])
    await _approve()
    status, balance, rows = await _read(db)
    assert (status, balance) == (True, 111_000)
    _assert_one_payment(rows)


async def test_commit_failure_leaves_payment_retryable(db):
    flushed = []

    def fail_commit(session):
        session.flush()
        flushed.append(True)
        raise OperationalError("COMMIT", {}, RuntimeError("commit unavailable"))

    sync_session = db.sessions.class_.sync_session_class
    event.listen(sync_session, "before_commit", fail_commit)
    try:
        with pytest.raises(OperationalError):
            await _approve()
    finally:
        event.remove(sync_session, "before_commit", fail_commit)
    assert flushed == [True]
    status, balance, rows = await _read(db)
    assert (status, balance, rows) == (False, 1000, [])
    await _approve()
    status, balance, rows = await _read(db)
    assert (status, balance) == (True, 111_000)
    _assert_one_payment(rows)


async def test_missing_wallet_does_not_claim_invoice(db):
    async with db.sessions() as session:
        await session.execute(delete(User).where(User.id == USER))
        await session.commit()
    with pytest.raises(LookupError):
        await _approve()
    status, balance, rows = await _read(db)
    assert (status, balance, rows) == (False, None, [])
    async with db.sessions() as session:
        session.add(User(id=USER, amount=1000))
        await session.commit()
    await _approve()
    status, balance, rows = await _read(db)
    assert (status, balance) == (True, 111_000)
    _assert_one_payment(rows)


async def test_already_claimed_invoice_is_not_recredited(db):
    async with db.sessions() as session:
        invoice = await session.get(AutoCard, CODE)
        invoice.status = True
        await session.commit()
    assert await _approve() is None
    assert await _read(db) == (True, 1000, [])
