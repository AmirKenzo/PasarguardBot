from sqlalchemy import delete, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.future import select

from app.db.base import AsyncSessionLocal as Session
from app.db.models.reseller_billing_snapshots import ResellerBillingSnapshot
from app.logger import get_logger
from app.utils.formatting.conversions import as_int

log = get_logger(__name__)


class ResellerBillingSnapshotCRUD:
    async def get_latest_snapshot(self, account_code) -> ResellerBillingSnapshot | None:
        account_code = as_int(account_code)
        if account_code is None:
            return None
        try:
            async with Session() as session:
                result = await session.execute(
                    select(ResellerBillingSnapshot)
                    .where(ResellerBillingSnapshot.account_code == account_code)
                    .order_by(ResellerBillingSnapshot.snapshot_at.desc())
                    .limit(1)
                )
                return result.scalars().first()
        except SQLAlchemyError as e:
            log.error("Failed to get billing snapshot: %s", e)
            return None

    async def get_snapshots(self, account_code, *, limit: int = 15, offset: int = 0) -> list[ResellerBillingSnapshot]:
        account_code = as_int(account_code)
        if account_code is None:
            return []
        try:
            async with Session() as session:
                result = await session.execute(
                    select(ResellerBillingSnapshot)
                    .where(ResellerBillingSnapshot.account_code == account_code)
                    .order_by(ResellerBillingSnapshot.snapshot_at.desc())
                    .offset(offset)
                    .limit(limit)
                )
                return list(result.scalars().all())
        except SQLAlchemyError as e:
            log.error("Failed to list billing snapshots: %s", e)
            return []

    async def get_usage_totals(self, account_code) -> tuple[int, int]:
        account_code = as_int(account_code)
        if account_code is None:
            return 0, 0
        try:
            async with Session() as session:
                result = await session.execute(
                    select(
                        func.count(ResellerBillingSnapshot.id),
                        func.coalesce(func.sum(ResellerBillingSnapshot.billed_amount), 0),
                    ).where(ResellerBillingSnapshot.account_code == account_code)
                )
                row = result.one()
                return int(row[0] or 0), int(row[1] or 0)
        except SQLAlchemyError as e:
            log.error("Failed to sum billing snapshots: %s", e)
            return 0, 0

    async def delete_snapshots_for_account(self, account_code) -> bool:
        account_code = as_int(account_code)
        if account_code is None:
            return False
        try:
            async with Session() as session:
                await session.execute(
                    delete(ResellerBillingSnapshot).where(ResellerBillingSnapshot.account_code == account_code)
                )
                await session.commit()
                return True
        except SQLAlchemyError as e:
            log.error("Failed to delete billing snapshots: %s", e)
            return False

    async def add_snapshot(
        self,
        account_code: int,
        used_traffic: int,
        billed_amount: int,
        snapshot_at: int,
        *,
        used_bytes: int | None = None,
        unit_price: float | None = None,
        period_start: int | None = None,
        is_debt: bool = False,
    ) -> bool:
        try:
            async with Session() as session:
                session.add(
                    ResellerBillingSnapshot(
                        account_code=account_code,
                        used_traffic=used_traffic,
                        billed_amount=billed_amount,
                        snapshot_at=snapshot_at,
                        used_bytes=used_bytes,
                        unit_price=unit_price,
                        period_start=period_start,
                        is_debt=is_debt or None,
                    )
                )
                await session.commit()
                return True
        except SQLAlchemyError as e:
            log.error("Failed to add billing snapshot: %s", e)
            return False

    async def add_hourly_charge(
        self, account_code: int, amount: int, minutes: int, charged_at: int, *, hourly_rate: float | None = None
    ) -> bool:
        """Fold one hourly-plan charge into the row of the clock hour it belongs to.

        The billing job runs every minute; one row per hour keeps the ledger readable and small.
        """
        bucket = int(charged_at) - int(charged_at) % 3600
        try:
            async with Session() as session:
                stmt = select(ResellerBillingSnapshot).where(
                    ResellerBillingSnapshot.account_code == account_code,
                    ResellerBillingSnapshot.snapshot_at == bucket,
                    ResellerBillingSnapshot.billed_minutes.is_not(None),
                )
                row = (await session.execute(stmt)).scalars().first()
                if row is None:
                    session.add(
                        ResellerBillingSnapshot(
                            account_code=account_code,
                            used_traffic=0,
                            billed_amount=int(amount),
                            billed_minutes=int(minutes),
                            snapshot_at=bucket,
                            unit_price=hourly_rate,
                        )
                    )
                else:
                    row.billed_amount = int(row.billed_amount or 0) + int(amount)
                    row.billed_minutes = int(row.billed_minutes or 0) + int(minutes)
                    if hourly_rate is not None:
                        row.unit_price = hourly_rate
                await session.commit()
                return True
        except SQLAlchemyError as e:
            log.error("Failed to add hourly charge: %s", e)
            return False

    async def get_previous_usage_snapshots(
        self, rows: list[ResellerBillingSnapshot]
    ) -> dict[int, ResellerBillingSnapshot]:
        """For each usage row, the usage row of the same account right before it (keyed by row id)."""
        previous: dict[int, ResellerBillingSnapshot] = {}
        targets = [row for row in rows if row.billed_minutes is None]
        if not targets:
            return previous
        try:
            async with Session() as session:
                for row in targets:
                    result = await session.execute(
                        select(ResellerBillingSnapshot)
                        .where(
                            ResellerBillingSnapshot.account_code == row.account_code,
                            ResellerBillingSnapshot.billed_minutes.is_(None),
                            (ResellerBillingSnapshot.snapshot_at < row.snapshot_at)
                            | (
                                (ResellerBillingSnapshot.snapshot_at == row.snapshot_at)
                                & (ResellerBillingSnapshot.id < row.id)
                            ),
                        )
                        .order_by(ResellerBillingSnapshot.snapshot_at.desc(), ResellerBillingSnapshot.id.desc())
                        .limit(1)
                    )
                    found = result.scalars().first()
                    if found is not None:
                        previous[int(row.id)] = found
        except SQLAlchemyError as e:
            log.error("Failed to load previous billing snapshots: %s", e)
        return previous

    async def sum_billed_since(self, account_codes: list[int], since: int) -> dict[int, int]:
        """Total charged per account since ``since`` (both hourly buckets and usage rows)."""
        if not account_codes:
            return {}
        try:
            async with Session() as session:
                rows = await session.execute(
                    select(ResellerBillingSnapshot.account_code, func.sum(ResellerBillingSnapshot.billed_amount))
                    .where(
                        ResellerBillingSnapshot.account_code.in_(account_codes),
                        ResellerBillingSnapshot.snapshot_at >= since,
                    )
                    .group_by(ResellerBillingSnapshot.account_code)
                )
                return {int(code): int(total or 0) for code, total in rows.all()}
        except SQLAlchemyError as e:
            log.error("Failed to sum billed amounts: %s", e)
            return {}

    async def delete_snapshots_before(self, cutoff_ts: int) -> int:
        """Delete billing snapshots older than cutoff timestamp."""
        try:
            async with Session() as session:
                stmt = delete(ResellerBillingSnapshot).where(ResellerBillingSnapshot.snapshot_at < cutoff_ts)
                result = await session.execute(stmt)
                await session.commit()
                return int(result.rowcount or 0)
        except SQLAlchemyError as e:
            log.error("Failed to purge old billing snapshots: %s", e)
            return 0
