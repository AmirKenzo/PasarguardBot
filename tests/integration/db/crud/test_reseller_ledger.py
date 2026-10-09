"""Reseller ledger: hourly charges fold into one row per clock hour, and events are stored per account/user."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.crud import reseller_billing_snapshots, reseller_events
from app.db.crud.reseller_billing_snapshots import ResellerBillingSnapshotCRUD
from app.db.crud.reseller_events import ResellerEventCRUD
from app.db.models.reseller_billing_snapshots import ResellerBillingSnapshot
from app.db.models.reseller_events import ResellerEvent

HOUR = 3600
BASE = 1_000 * HOUR  # a clock-hour boundary


@pytest.fixture
async def db(monkeypatch: pytest.MonkeyPatch, tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'ledger.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(
            ResellerEvent.metadata.create_all,
            tables=[ResellerBillingSnapshot.__table__, ResellerEvent.__table__],
        )
    maker = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(reseller_billing_snapshots, "Session", maker)
    monkeypatch.setattr(reseller_events, "Session", maker)
    yield
    await engine.dispose()


async def test_minute_charges_fold_into_one_hourly_row(db):
    crud = ResellerBillingSnapshotCRUD()
    for minute in range(3):
        await crud.add_hourly_charge(7, 250, 1, BASE + 60 * (minute + 1))

    rows = await crud.get_snapshots(7)
    assert len(rows) == 1
    assert rows[0].snapshot_at == BASE
    assert rows[0].billed_amount == 750
    assert rows[0].billed_minutes == 3


async def test_next_clock_hour_starts_a_new_row(db):
    crud = ResellerBillingSnapshotCRUD()
    await crud.add_hourly_charge(7, 250, 1, BASE + 60)
    await crud.add_hourly_charge(7, 250, 1, BASE + HOUR + 60)
    assert len(await crud.get_snapshots(7)) == 2


async def test_hourly_bucket_never_merges_into_a_usage_row(db):
    crud = ResellerBillingSnapshotCRUD()
    await crud.add_snapshot(7, 10_000, 40, BASE)
    await crud.add_hourly_charge(7, 250, 1, BASE + 60)
    rows = await crud.get_snapshots(7)
    assert sorted(r.billed_minutes or 0 for r in rows) == [0, 1]


async def test_sum_billed_since_groups_by_account(db):
    crud = ResellerBillingSnapshotCRUD()
    await crud.add_hourly_charge(1, 100, 1, BASE + 60)
    await crud.add_snapshot(2, 5_000, 30, BASE + 120)
    await crud.add_snapshot(2, 9_000, 20, BASE - 10 * HOUR)
    assert await crud.sum_billed_since([1, 2], BASE) == {1: 100, 2: 30}


async def test_events_filter_by_account_and_user(db):
    crud = ResellerEventCRUD()
    await crud.add_event(kind="purchase", title="buy", account_code=1, telegram_id=9, data={"amount": 500})
    await crud.add_event(kind="pause", title="pause", account_code=1, telegram_id=9)
    await crud.add_event(kind="low_balance", title="low", telegram_id=9)
    await crud.add_event(kind="purchase", title="other", account_code=2, telegram_id=8)

    account_rows, account_total = await crud.list_events(account_code=1)
    assert account_total == 2
    assert {row.kind for row in account_rows} == {"purchase", "pause"}

    user_rows, user_total = await crud.list_events(telegram_id=9, kinds=("purchase", "low_balance"))
    assert user_total == 2
    purchase = next(row for row in user_rows if row.kind == "purchase")
    assert ResellerEventCRUD.load_data(purchase) == {"amount": 500}
