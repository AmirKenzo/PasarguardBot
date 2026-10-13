"""Group wallet charge: one UPDATE per chunk, all in a single transaction."""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.crud import user as user_crud
from app.db.crud.user import UserCRUD
from app.db.models.user import User

SEEDED = {1: 100, 2: 0, 3: None, 4: 50}


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch, tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'balance.db'}")

    async def setup():
        async with engine.begin() as conn:
            await conn.run_sync(User.metadata.create_all, tables=[User.__table__])
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as session:
            session.add_all([User(id=uid, amount=amount) for uid, amount in SEEDED.items()])
            await session.commit()
        return maker

    maker = asyncio.run(setup())
    monkeypatch.setattr(user_crud, "Session", maker)
    return maker


def _balances(maker) -> dict[int, int | None]:
    async def run():
        async with maker() as session:
            rows = await session.execute(select(User.id, User.amount))
            return dict(rows.all())

    return asyncio.run(run())


def test_bulk_charge_selected_ids(db) -> None:
    updated = asyncio.run(UserCRUD().add_balance_bulk(1_000, [1, 3, 3, 999, 0]))

    assert updated == 2
    assert _balances(db) == {1: 1_100, 2: 0, 3: 1_000, 4: 50}


def test_bulk_charge_all_users(db) -> None:
    updated = asyncio.run(UserCRUD().add_balance_bulk(500))

    assert updated == len(SEEDED)
    assert _balances(db) == {1: 600, 2: 500, 3: 500, 4: 550}


def test_bulk_charge_chunks_ids(db, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(user_crud, "BULK_BALANCE_CHUNK_SIZE", 2)

    updated = asyncio.run(UserCRUD().add_balance_bulk(10, [4, 3, 2, 1]))

    assert updated == 4
    assert _balances(db) == {1: 110, 2: 10, 3: 10, 4: 60}


def test_bulk_charge_empty_ids_updates_nothing(db) -> None:
    assert asyncio.run(UserCRUD().add_balance_bulk(10, [])) == 0
    assert _balances(db) == {1: 100, 2: 0, 3: 0, 4: 50}
