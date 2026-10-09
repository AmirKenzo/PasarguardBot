"""Usage billing writes wallet, account baseline and ledger row together, or not at all."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.crud import reseller_billing_snapshots
from app.db.crud.reseller_billing_snapshots import (
    USAGE_CHARGED,
    USAGE_DEBT,
    USAGE_INSUFFICIENT,
    USAGE_STALE,
    ResellerBillingSnapshotCRUD,
)
from app.db.models.reseller_accounts import ResellerAccount
from app.db.models.reseller_billing_snapshots import ResellerBillingSnapshot
from app.db.models.user import User

GB = 1024**3
NOW = 2_000_000_000


@pytest.fixture
async def maker(monkeypatch: pytest.MonkeyPatch, tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'usage.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(
            User.metadata.create_all,
            tables=[User.__table__, ResellerAccount.__table__, ResellerBillingSnapshot.__table__],
        )
    maker = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(reseller_billing_snapshots, "Session", maker)
    async with maker() as session:
        session.add(User(id=7, amount=10_000))
        session.add(
            ResellerAccount(
                code=1,
                telegram_id=7,
                panel_code=1,
                username="res",
                password_encrypted="x",
                pricing_mode="usage",
                status="active",
                billed_traffic=100 * GB,
            )
        )
        await session.commit()
    yield maker
    await engine.dispose()


async def _charge(baseline, used, charge, *, allow_debt=True):
    return await ResellerBillingSnapshotCRUD().record_usage_charge(
        1,
        baseline=baseline,
        used_traffic=used,
        used_bytes=used - (baseline or 0),
        charge=charge,
        unit_price=1000,
        charged_at=NOW,
        period_start=NOW - 60,
        allow_debt=allow_debt,
    )


async def _state(maker):
    async with maker() as session:
        user = await session.get(User, 7)
        account = await session.get(ResellerAccount, 1)
        rows = (await session.execute(ResellerBillingSnapshot.__table__.select())).fetchall()
        return int(user.amount), account.billed_traffic, rows


async def test_charge_moves_wallet_baseline_and_ledger_together(maker):
    result = await _charge(100 * GB, 102 * GB, 2_000)
    assert result.status == USAGE_CHARGED and result.balance == 8_000
    balance, baseline, rows = await _state(maker)
    assert (balance, baseline, len(rows)) == (8_000, 102 * GB, 1)


async def test_stale_baseline_writes_nothing(maker):
    # Another run already billed from 100 GB; a second charge from the same baseline must not repeat it.
    await _charge(100 * GB, 102 * GB, 2_000)
    assert (await _charge(100 * GB, 102 * GB, 2_000)).status == USAGE_STALE
    balance, baseline, rows = await _state(maker)
    assert (balance, baseline, len(rows)) == (8_000, 102 * GB, 1)


async def test_insufficient_without_debt_writes_nothing(maker):
    result = await _charge(100 * GB, 120 * GB, 20_000, allow_debt=False)
    assert result.status == USAGE_INSUFFICIENT
    balance, baseline, rows = await _state(maker)
    assert (balance, baseline, rows) == (10_000, 100 * GB, [])


async def test_debt_goes_negative_and_is_flagged(maker):
    result = await _charge(100 * GB, 120 * GB, 20_000)
    assert result.status == USAGE_DEBT and result.balance == -10_000
    _, baseline, rows = await _state(maker)
    assert baseline == 120 * GB and rows[0].is_debt


async def test_purged_ledger_does_not_rebill_old_usage(maker):
    # History is deleted; the baseline on the account still says 100 GB were billed.
    await ResellerBillingSnapshotCRUD().delete_snapshots_before(NOW + 1)
    result = await _charge(100 * GB, 101 * GB, 1_000)
    assert result.status == USAGE_CHARGED and result.balance == 9_000
