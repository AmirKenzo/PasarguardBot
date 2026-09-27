import random
import string
import time

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select

from app.db.base import AsyncSessionLocal as Session
from app.db.models.stars_transaction import StarsTransaction
from app.db.models.user import User
from app.jobs.payments.stars import STARS_INVOICE_TTL_SECONDS


def _new_invoice_no() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=8))


class StarsTransactionCRUD:
    async def create(
        self,
        user_id: int,
        amount: int,
        stars: int,
        status: str = "pending",
    ) -> StarsTransaction:
        last_error: Exception | None = None
        for _ in range(5):
            try:
                async with Session() as session:
                    tx = StarsTransaction(
                        user_id=user_id,
                        amount=amount,
                        stars=stars,
                        status=status,
                        invoice_no=_new_invoice_no(),
                        created_at=int(time.time()),
                    )
                    session.add(tx)
                    await session.commit()
                    return tx
            except IntegrityError as e:
                last_error = e
                continue
        raise ValueError(f"Could not generate unique invoice number: {last_error}")

    async def get(self, tx_id: int) -> StarsTransaction | None:
        async with Session() as session:
            result = await session.execute(select(StarsTransaction).filter_by(id=tx_id))
            return result.scalar_one_or_none()

    async def update(self, tx_id: int, **kwargs) -> StarsTransaction | None:
        async with Session() as session:
            result = await session.execute(select(StarsTransaction).filter_by(id=tx_id))
            tx = result.scalar_one_or_none()
            if tx:
                for key, value in kwargs.items():
                    if hasattr(tx, key):
                        setattr(tx, key, value)
                await session.commit()
                return tx
            return None

    async def approve_and_credit(
        self, tx_id: int, total_amount: int, paid_at: int
    ) -> tuple[StarsTransaction, int] | None:
        async with Session() as session, session.begin():
            tx_stmt = select(StarsTransaction).where(StarsTransaction.id == tx_id)
            dialect = session.bind.dialect if session.bind is not None else None
            if dialect and dialect.name != "sqlite":
                tx_stmt = tx_stmt.with_for_update()
            tx = (await session.execute(tx_stmt)).scalar_one_or_none()
            if not tx or tx.status != "pending":
                return None
            if int(tx.created_at or 0) + STARS_INVOICE_TTL_SECONDS <= paid_at:
                tx.status = "expired"
                return None

            user_stmt = select(User).where(User.id == tx.user_id)
            if dialect and dialect.name != "sqlite":
                user_stmt = user_stmt.with_for_update()
            user = (await session.execute(user_stmt)).scalar_one_or_none()
            if not user:
                return None

            user.amount = int(user.amount or 0) + int(total_amount)
            tx.status = "approved"
            tx.paid_at = paid_at
            return tx, int(user.amount or 0)

    async def get_user_stats(self, user_id: int) -> dict:
        """Approved stars transaction count and total amount for one user."""
        async with Session() as session:
            stmt = select(
                func.count().label("count"),
                func.sum(StarsTransaction.amount).label("total_amount"),
            ).where(StarsTransaction.user_id == user_id, StarsTransaction.status == "approved")
            row = (await session.execute(stmt)).one()
            return {"count": int(row.count or 0), "total_amount": int(row.total_amount or 0)}

    async def get_user_all_transactions(self, user_id: int, *, limit: int | None = None):
        """All stars transactions for a user, newest first."""
        async with Session() as session:
            stmt = (
                select(StarsTransaction)
                .where(StarsTransaction.user_id == user_id)
                .order_by(StarsTransaction.created_at.desc())
            )
            if limit is not None:
                stmt = stmt.limit(limit)
            result = await session.execute(stmt)
            return result.scalars().all()

    async def count_user_transactions(self, user_id: int) -> int:
        async with Session() as session:
            result = await session.execute(
                select(func.count()).select_from(StarsTransaction).where(StarsTransaction.user_id == user_id)
            )
            return int(result.scalar() or 0)

    async def get_user_transaction_by_id(self, user_id: int, tx_id: int):
        async with Session() as session:
            result = await session.execute(
                select(StarsTransaction).where(StarsTransaction.user_id == user_id, StarsTransaction.id == tx_id)
            )
            return result.scalar_one_or_none()

    async def get_global_stats(self) -> dict:
        """Global stats: count and total amount of approved stars payments."""
        async with Session() as session:
            stmt = select(
                func.count().label("count"),
                func.sum(StarsTransaction.amount).label("total_amount"),
            ).where(StarsTransaction.status == "approved")
            result = await session.execute(stmt)
            row = result.one()
            return {"count": int(row.count or 0), "total_amount": int(row.total_amount or 0)}

    async def get_period_stats(self, start_ts: int, end_ts: int | None = None) -> dict:
        """Approved stars payments in [start_ts, end_ts) by paid_at or created_at fallback."""
        async with Session() as session:
            paid_at = func.coalesce(StarsTransaction.paid_at, StarsTransaction.created_at)
            cond = (StarsTransaction.status == "approved") & (paid_at >= start_ts)
            if end_ts is not None:
                cond = cond & (paid_at < end_ts)
            stmt = select(
                func.count().label("count"),
                func.sum(StarsTransaction.amount).label("total_amount"),
            ).where(cond)
            row = (await session.execute(stmt)).one()
            return {"count": int(row.count or 0), "total_amount": int(row.total_amount or 0)}
