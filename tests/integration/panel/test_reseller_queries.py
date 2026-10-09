"""Admin panel reseller queries: ledger, revenue buckets, status breakdown and plan links."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models.reseller_accounts import ResellerAccount
from app.db.models.reseller_billing_snapshots import ResellerBillingSnapshot
from app.db.models.reseller_events import ResellerEvent
from app.db.models.user import User
from app.panel import queries

HOUR = 3600


@pytest.fixture
async def db(monkeypatch: pytest.MonkeyPatch, tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'panel.db'}")
    tables = [table.__table__ for table in (ResellerAccount, ResellerBillingSnapshot, ResellerEvent, User)]
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=tables)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(queries, "Session", maker)
    async with maker() as session:
        session.add_all(
            [
                _account(1, telegram_id=10, status="active", mode="hourly", plan_id=3),
                _account(2, telegram_id=10, status="paused", mode="usage", plan_id=3),
                _account(3, telegram_id=20, status="active", mode="fixed", plan_id=4),
                ResellerBillingSnapshot(account_code=1, used_traffic=0, billed_amount=100, snapshot_at=HOUR),
                ResellerBillingSnapshot(account_code=1, used_traffic=0, billed_amount=200, snapshot_at=5 * HOUR),
                ResellerBillingSnapshot(account_code=2, used_traffic=10, billed_amount=0, snapshot_at=5 * HOUR),
                ResellerBillingSnapshot(account_code=9, used_traffic=10, billed_amount=50, snapshot_at=6 * HOUR),
            ]
        )
        await session.commit()
    yield maker
    await engine.dispose()


def _account(code: int, *, telegram_id: int, status: str, mode: str, plan_id: int) -> ResellerAccount:
    return ResellerAccount(
        code=code,
        telegram_id=telegram_id,
        panel_code=1,
        username=f"res{code}",
        password_encrypted="x",
        plan_id=plan_id,
        pricing_mode=mode,
        status=status,
    )


async def test_ledger_skips_zero_rows_and_keeps_orphans(db):
    rows, total, billed = await queries.reseller_ledger()
    assert total == 3
    assert billed == 350
    assert [snapshot.billed_amount for snapshot, _ in rows] == [50, 200, 100]
    assert rows[0][1] is None
    assert rows[1][1].username == "res1"


async def test_ledger_filters_by_user_and_window(db):
    _, total, billed = await queries.reseller_ledger(telegram_id=10, since=2 * HOUR)
    assert (total, billed) == (1, 200)


async def test_billed_buckets_split_by_window(db):
    assert await queries.reseller_billed_buckets([0, 2 * HOUR, 10 * HOUR]) == [100, 250]


async def test_breakdown_and_plan_links(db):
    assert sorted(await queries.reseller_breakdown()) == [
        ("active", "fixed", 1),
        ("active", "hourly", 1),
        ("paused", "usage", 1),
    ]
    assert await queries.reseller_plan_link_counts() == {3: 2, 4: 1}
    burning = await queries.burning_resellers(("hourly", "usage"))
    assert [account.code for account in burning] == [1]
