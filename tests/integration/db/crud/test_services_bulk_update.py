"""Service flag bulk update: one UPDATE per chunk, all in a single transaction."""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.crud import services as services_crud
from app.db.crud.services import ServiceCRUD
from app.db.models.services import Service

CODES = [1, 2, 3, 4, 5]


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch, tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'services.db'}")

    async def setup():
        async with engine.begin() as conn:
            await conn.run_sync(Service.metadata.create_all, tables=[Service.__table__])
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as session:
            session.add_all([Service(code=code, username=f"u{code}", warning=0) for code in CODES])
            await session.commit()
        return maker

    maker = asyncio.run(setup())
    monkeypatch.setattr(services_crud, "Session", maker)
    return maker


def _flags(maker) -> dict[int, tuple[bool, int, int | None]]:
    async def run():
        async with maker() as session:
            rows = await session.execute(
                select(Service.code, Service.expire_notified, Service.warning, Service.warning_time)
            )
            return {code: (bool(notified), warning, warning_time) for code, notified, warning, warning_time in rows}

    return asyncio.run(run())


def test_bulk_update_sets_values_on_selected_codes(db) -> None:
    updated = asyncio.run(ServiceCRUD().update_services_bulk([2, 4, 4, "5", None, 999], warning=1, warning_time=77))

    assert updated == 3
    flags = _flags(db)
    assert {code for code, (_, warning, _) in flags.items() if warning == 1} == {2, 4, 5}
    assert flags[2] == (False, 1, 77)
    assert flags[1] == (False, 0, None)


def test_bulk_update_chunks_codes(db, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(services_crud, "BULK_UPDATE_CHUNK_SIZE", 2)

    updated = asyncio.run(ServiceCRUD().update_services_bulk(CODES, expire_notified=True))

    assert updated == len(CODES)
    assert all(notified for notified, _, _ in _flags(db).values())


def test_bulk_update_ignores_empty_input_and_unknown_fields(db) -> None:
    crud = ServiceCRUD()
    assert asyncio.run(crud.update_services_bulk([], expire_notified=True)) == 0
    assert asyncio.run(crud.update_services_bulk([1], not_a_column=1)) == 0
    assert not any(notified for notified, _, _ in _flags(db).values())
