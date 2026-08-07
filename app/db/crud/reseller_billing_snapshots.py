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

    async def add_snapshot(self, account_code: int, used_traffic: int, billed_amount: int, snapshot_at: int) -> bool:
        try:
            async with Session() as session:
                session.add(
                    ResellerBillingSnapshot(
                        account_code=account_code,
                        used_traffic=used_traffic,
                        billed_amount=billed_amount,
                        snapshot_at=snapshot_at,
                    )
                )
                await session.commit()
                return True
        except SQLAlchemyError as e:
            log.error("Failed to add billing snapshot: %s", e)
            return False

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
