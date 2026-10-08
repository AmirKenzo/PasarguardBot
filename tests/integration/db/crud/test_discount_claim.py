"""Discount usage limits hold under concurrent purchases (in-memory SQLite)."""

from __future__ import annotations

import asyncio
import time

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.crud import discount_codes
from app.db.models.discount_codes import DiscountCode

OWNER = 10
OTHER = 20


def _code(code: str, **overrides) -> DiscountCode:
    fields = {
        "code": code,
        "discount_percentage": 50,
        "is_public": True,
        "user_id": None,
        "expiration_date": int(time.time()) + 3600,
        "usage_limit": 1,
        "times_used": 0,
    }
    fields.update(overrides)
    return DiscountCode(**fields)


@pytest.fixture
def manager(monkeypatch: pytest.MonkeyPatch, tmp_path):
    # A file database gives each session its own connection, like MySQL; the shared
    # in-memory connection would let one session's rollback undo another's update.
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'discounts.db'}")
    cleared: list[str] = []

    async def setup():
        async with engine.begin() as conn:
            await conn.run_sync(DiscountCode.metadata.create_all, tables=[DiscountCode.__table__])
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as session:
            session.add_all(
                [
                    _code("ONCE"),
                    _code("THREE", usage_limit=3),
                    _code("EXPIRED", expiration_date=int(time.time()) - 10),
                    _code("PRIVATE", is_public=False, user_id=OWNER),
                ]
            )
            await session.commit()
        return maker

    async def clear_sticky(code: str) -> None:
        cleared.append(code)

    monkeypatch.setattr(discount_codes, "Session", asyncio.run(setup()))
    monkeypatch.setattr(discount_codes, "clear_sticky_for_code", clear_sticky)
    mgr = discount_codes.DiscountCodeManager()
    mgr.cleared = cleared
    return mgr


async def _times_used(code: str) -> int:
    async with discount_codes.Session() as session:
        row = await session.get(DiscountCode, (await _id(session, code)))
        return int(row.times_used)


async def _id(session, code: str) -> int:
    from sqlalchemy import select

    return (await session.execute(select(DiscountCode.id).where(DiscountCode.code == code))).scalar_one()


def test_concurrent_claims_respect_usage_limit(manager) -> None:
    async def run():
        return await asyncio.gather(*(manager.claim_discount_use("THREE", OWNER) for _ in range(10)))

    results = asyncio.run(run())

    assert sum(results) == 3
    assert asyncio.run(_times_used("THREE")) == 3
    assert manager.cleared == ["THREE"]


def test_single_use_code_is_claimed_once(manager) -> None:
    assert asyncio.run(manager.claim_discount_use("ONCE", OWNER)) is True
    assert asyncio.run(manager.claim_discount_use("ONCE", OTHER)) is False


def test_release_gives_the_use_back(manager) -> None:
    assert asyncio.run(manager.claim_discount_use("ONCE", OWNER)) is True
    asyncio.run(manager.release_discount_use("ONCE"))
    assert asyncio.run(_times_used("ONCE")) == 0
    assert asyncio.run(manager.claim_discount_use("ONCE", OTHER)) is True


def test_release_never_goes_below_zero(manager) -> None:
    asyncio.run(manager.release_discount_use("ONCE"))
    assert asyncio.run(_times_used("ONCE")) == 0


def test_expired_code_cannot_be_claimed(manager) -> None:
    assert asyncio.run(manager.claim_discount_use("EXPIRED", OWNER)) is False


def test_private_code_only_for_its_owner(manager) -> None:
    assert asyncio.run(manager.claim_discount_use("PRIVATE", OTHER)) is False
    assert asyncio.run(manager.claim_discount_use("PRIVATE", OWNER)) is True


def test_unknown_code_cannot_be_claimed(manager) -> None:
    assert asyncio.run(manager.claim_discount_use("NOPE", OWNER)) is False
