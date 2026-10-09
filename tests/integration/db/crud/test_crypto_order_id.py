"""Crypto invoice numbers never collide with stored invoices, and a failed insert is reported."""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import BigInteger, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import NullPool

from app.db.crud import cryptopayments
from app.db.models.cryptopayments import CryptoPayments


@compiles(BigInteger, "sqlite")
def _sqlite_bigint(type_, compiler, **kw) -> str:
    return "INTEGER"


@pytest.fixture(autouse=True)
def db(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'crypto.db'}", poolclass=NullPool)

    async def setup():
        async with engine.begin() as conn:
            await conn.run_sync(CryptoPayments.metadata.create_all, tables=[CryptoPayments.__table__])
        return async_sessionmaker(engine, expire_on_commit=False)

    monkeypatch.setattr(cryptopayments, "Session", asyncio.run(setup()))


def _add(order_id: int, msg_id: int | None = None) -> dict:
    return asyncio.run(
        cryptopayments.add_order_crypto_payment(
            order_id=order_id, user_id=1, arz="trx", amount="1.5", amount_irt=1000, createtime=0, msg_id=msg_id
        )
    )


def test_allocated_id_skips_taken_numbers(monkeypatch: pytest.MonkeyPatch) -> None:
    taken = cryptopayments.ORDER_ID_MIN + 7
    assert _add(taken)["success"] is True
    picks = iter([7, 7, 8])
    monkeypatch.setattr(cryptopayments.secrets, "randbelow", lambda n: next(picks))
    assert asyncio.run(cryptopayments.allocate_order_id()) == cryptopayments.ORDER_ID_MIN + 8


def test_allocation_gives_up_when_every_pick_is_taken(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _add(cryptopayments.ORDER_ID_MIN)["success"] is True
    monkeypatch.setattr(cryptopayments.secrets, "randbelow", lambda n: 0)
    assert asyncio.run(cryptopayments.allocate_order_id(attempts=3)) is None


def test_duplicate_insert_reports_failure() -> None:
    assert _add(60000)["success"] is True
    assert _add(60000)["success"] is False


def test_msg_id_is_attached_after_sending() -> None:
    assert _add(61000)["success"] is True
    asyncio.run(cryptopayments.set_order_msg_id(61000, 42))

    async def read() -> int | None:
        async with cryptopayments.Session() as session:
            return (
                await session.execute(select(CryptoPayments.msg_id).where(CryptoPayments.order_id == 61000))
            ).scalar_one()

    assert asyncio.run(read()) == 42
