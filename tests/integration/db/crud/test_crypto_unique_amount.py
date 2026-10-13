"""Concurrent crypto invoices of one network never end up with amounts one transfer could match."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from sqlalchemy import BigInteger, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.pool import NullPool

from app.db.crud import cryptopayments
from app.db.models.cryptopayments import CryptoPayments
from app.services.pricing import crypto_amounts
from app.services.pricing.crypto_amounts import crypto_amount_picker


@compiles(BigInteger, "sqlite")
def _sqlite_bigint(type_, compiler, **kw) -> str:
    return "INTEGER"


@pytest.fixture(autouse=True)
def db(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'amounts.db'}", poolclass=NullPool)

    async def setup():
        async with engine.begin() as conn:
            await conn.run_sync(CryptoPayments.metadata.create_all, tables=[CryptoPayments.__table__])
        return async_sessionmaker(engine, expire_on_commit=False)

    monkeypatch.setattr(cryptopayments, "Session", asyncio.run(setup()))


async def _create(order_id: int, pick_amount) -> dict:
    return await cryptopayments.add_order_with_unique_amount(
        order_id=order_id, user_id=1, arz="trx", amount_irt=100_000, createtime=0, pick_amount=pick_amount
    )


async def _pending_amounts() -> dict[int, str]:
    async with cryptopayments.Session() as session:
        result = await session.execute(
            select(CryptoPayments.order_id, CryptoPayments.amount).where(CryptoPayments.status == "Pending")
        )
        return {int(order_id): str(amount) for order_id, amount in result.all()}


def _assert_pairwise_distinct(amounts: list[str]) -> None:
    for i, left in enumerate(amounts):
        for right in amounts[i + 1 :]:
            assert not cryptopayments.amounts_collide(left, right), (left, right)


def test_concurrent_invoices_get_distinct_amounts(monkeypatch: pytest.MonkeyPatch) -> None:
    # A narrow dust range forces the concurrent picks to collide and be resolved by the re-check.
    monkeypatch.setattr(crypto_amounts.random, "uniform", lambda a, b: 0.0)
    picker = crypto_amount_picker("trx", SimpleNamespace(arz_trx=10_000), 100_000)

    async def scenario():
        results = await asyncio.gather(*(_create(60_000 + i, picker) for i in range(8)))
        return results, await _pending_amounts()

    results, stored = asyncio.run(scenario())
    assert all(r["success"] for r in results)
    assert len(stored) == 8
    assert sorted(str(r["record"]["amount"]) for r in results) == sorted(stored.values())
    _assert_pairwise_distinct(list(stored.values()))


def test_stale_pick_is_regenerated_after_insert() -> None:
    stale_then_fresh = iter([1.5, 1.5, 2.25])

    async def stale_picker(_reserved: set[str]) -> float:
        # Ignores what it is told is reserved, like a read that raced another insert.
        return next(stale_then_fresh)

    async def scenario():
        first = await _create(70_001, stale_picker)
        second = await _create(70_002, stale_picker)
        return first, second, await _pending_amounts()

    first, second, stored = asyncio.run(scenario())
    assert first["record"]["amount"] == 1.5
    assert second["record"]["amount"] == 2.25
    assert stored == {70_001: "1.5", 70_002: "2.25"}


def test_neighbor_amount_counts_as_collision() -> None:
    picks = iter([1.5, 1.500001, 1.500003])

    async def picker(_reserved: set[str]) -> float:
        return next(picks)

    async def scenario():
        await _create(71_001, picker)
        second = await _create(71_002, picker)
        return second, await _pending_amounts()

    second, stored = asyncio.run(scenario())
    assert second["record"]["amount"] == 1.500003
    assert stored == {71_001: "1.5", 71_002: "1.500003"}


def test_invoice_is_discarded_when_no_unique_amount_is_found() -> None:
    async def always_same(_reserved: set[str]) -> float:
        return 3.0

    async def scenario():
        first = await _create(72_001, always_same)
        second = await cryptopayments.add_order_with_unique_amount(
            order_id=72_002,
            user_id=1,
            arz="trx",
            amount_irt=100_000,
            createtime=0,
            pick_amount=always_same,
            attempts=3,
        )
        return first, second, await _pending_amounts()

    first, second, stored = asyncio.run(scenario())
    assert first["success"] is True
    assert second["success"] is False
    assert stored == {72_001: "3.0"}
