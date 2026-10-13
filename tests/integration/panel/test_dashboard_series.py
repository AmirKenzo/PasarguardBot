"""Dashboard day series aggregated in SQL must bucket exactly like the old per-row bisect over Tehran midnights."""

from __future__ import annotations

import random
from bisect import bisect_right

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models.reseller_billing_snapshots import ResellerBillingSnapshot
from app.db.models.user import User
from app.panel import queries
from app.services.billing import payment_stats

DAYS = 14


def _legacy_buckets(boundaries: list[int], rows: list[tuple[int | None, int]]) -> list[int]:
    """The previous Python-side algorithm: bisect every in-range timestamp into its window."""
    totals = [0] * (len(boundaries) - 1)
    for ts, value in rows:
        if ts and boundaries[0] <= ts < boundaries[-1]:
            totals[bisect_right(boundaries, ts) - 1] += value
    return totals


def _timestamps(boundaries: list[int], count: int) -> list[int | None]:
    """Random timestamps plus every value right around each Tehran midnight, some outside the range."""
    rng = random.Random(42)
    edges = [edge + delta for edge in boundaries for delta in (-1, 0, 1)]
    spread = [rng.randint(boundaries[0] - 86400, boundaries[-1] + 86400) for _ in range(count)]
    return [*edges, *spread, None, 0]


@pytest.fixture
async def maker(monkeypatch: pytest.MonkeyPatch, tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'series.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=[User.__table__, ResellerBillingSnapshot.__table__])
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(queries, "Session", session_maker)
    yield session_maker
    await engine.dispose()


async def test_daily_series_signups_match_legacy_bucketing(maker, monkeypatch: pytest.MonkeyPatch):
    boundaries = payment_stats.tehran_day_boundaries(DAYS)
    stamps = _timestamps(boundaries, 2000)
    async with maker() as session:
        session.add_all([User(id=index + 1, time_s=ts) for index, ts in enumerate(stamps)])
        await session.commit()

    async def fake_revenue(bounds: list[int]) -> list[int]:
        return list(range(len(bounds) - 1))

    monkeypatch.setattr(payment_stats, "bucket_revenue", fake_revenue)
    monkeypatch.setattr(payment_stats, "tehran_day_boundaries", lambda days: boundaries)

    series = await queries.daily_series(DAYS)

    expected = _legacy_buckets(boundaries, [(ts, 1) for ts in stamps])
    assert [point["signups"] for point in series] == expected
    assert [point["ts"] for point in series] == boundaries[:-1]
    assert [point["revenue"] for point in series] == list(range(DAYS))


async def test_daily_series_zero_fills_empty_days(maker, monkeypatch: pytest.MonkeyPatch):
    async def no_revenue(bounds: list[int]) -> list[int]:
        return [0] * max(0, len(bounds) - 1)

    monkeypatch.setattr(payment_stats, "bucket_revenue", no_revenue)
    series = await queries.daily_series(3)
    assert [point["signups"] for point in series] == [0, 0, 0]
    assert await queries.daily_series(0) == []


async def test_billed_buckets_match_legacy_bucketing(maker):
    boundaries = payment_stats.tehran_day_boundaries(30)
    stamps = _timestamps(boundaries, 3000)
    rng = random.Random(7)
    rows = [(ts if ts is not None else 1, rng.choice((0, 0, 5, 120, 999))) for ts in stamps]
    async with maker() as session:
        session.add_all(
            [
                ResellerBillingSnapshot(account_code=1, used_traffic=0, billed_amount=amount, snapshot_at=ts)
                for ts, amount in rows
            ]
        )
        await session.commit()

    assert await queries.reseller_billed_buckets(boundaries) == _legacy_buckets(boundaries, rows)
    assert await queries.reseller_billed_buckets(boundaries[:1]) == []
