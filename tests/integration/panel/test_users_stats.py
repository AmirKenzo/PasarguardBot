"""Users page stats: rolling 24h join buckets, new buyers and active counts against SQLite."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models.services import Service
from app.db.models.user import User
from app.panel import queries

NOW = 1_800_000_000
DAY = queries.DAY


@pytest.fixture
async def maker(monkeypatch: pytest.MonkeyPatch, tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'users.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[User.__table__, Service.__table__])
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(queries, "Session", session_maker)
    monkeypatch.setattr(queries.time, "time", lambda: NOW)
    yield session_maker
    await engine.dispose()


async def test_users_stats_buckets_buyers_and_active(maker):
    users = [
        User(id=1, time_s=NOW - 10),
        User(id=2, time_s=NOW - DAY + 1),  # last 24h, test service only
        User(id=3, time_s=NOW - 60, status="ban"),  # last 24h, inactive, paid (is_test NULL)
        User(id=4, time_s=NOW - DAY),  # exactly 24h ago: still new (inclusive cutoff)
        User(id=5, time_s=NOW - 2 * DAY + 5),
        User(id=6, time_s=NOW - 7 * DAY),  # oldest bucket edge
        User(id=7, time_s=NOW - 7 * DAY - 1, status="BlockedBot"),  # outside the week
        User(id=8, time_s=None),
    ]
    services = [
        Service(code=1, username="s1", id=1, is_test=False),
        Service(code=2, username="s2", id=1, is_test=True),
        Service(code=3, username="s3", id=2, is_test=True),
        Service(code=4, username="s4", id=3, is_test=None),
        Service(code=5, username="s5", id=4, is_test=False),
    ]
    async with maker() as session:
        session.add_all([*users, *services])
        await session.commit()

    stats = await queries.users_stats()

    assert stats["new_daily"] == [1, 0, 0, 0, 0, 1, 4]
    assert stats["new_24h"] == 4
    assert stats["new_prev_24h"] == 1
    assert stats["new_7d"] == 6
    assert stats["new_buyers_24h"] == 3
    assert stats["active"] == 6
    assert stats["total"] == 8


async def test_users_stats_empty_database(maker):
    stats = await queries.users_stats()
    assert stats["new_daily"] == [0] * queries.NEW_USER_DAILY_BUCKETS
    assert stats["new_24h"] == stats["new_buyers_24h"] == stats["active"] == stats["total"] == 0
