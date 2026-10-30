"""Auto card-to-card invoice codes never collide with stored invoices, and a failed insert is reported."""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.crud import auto_card
from app.db.models.auto_card import AutoCard


@pytest.fixture(autouse=True)
def db(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'auto_card.db'}")

    async def setup():
        async with engine.begin() as conn:
            await conn.run_sync(AutoCard.metadata.create_all, tables=[AutoCard.__table__])
        return async_sessionmaker(engine, expire_on_commit=False)

    monkeypatch.setattr(auto_card, "GetDB", asyncio.run(setup()))


def _add(code: int):
    return asyncio.run(
        auto_card.CRUDAutoCard().create(code=code, time=0, amount=code * 10, first_amount=code, id=1, status=False)
    )


def test_allocated_code_skips_taken_numbers(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _add(auto_card.CODE_MIN + 7) is not None
    picks = iter([7, 7, 8])
    monkeypatch.setattr(auto_card.secrets, "randbelow", lambda n: next(picks))
    assert asyncio.run(auto_card.CRUDAutoCard().allocate_code()) == auto_card.CODE_MIN + 8


def test_allocation_gives_up_when_every_pick_is_taken(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _add(auto_card.CODE_MIN) is not None
    monkeypatch.setattr(auto_card.secrets, "randbelow", lambda n: 0)
    assert asyncio.run(auto_card.CRUDAutoCard().allocate_code(attempts=3)) is None


def test_duplicate_insert_reports_failure() -> None:
    assert _add(60000) is not None
    assert _add(60000) is None
