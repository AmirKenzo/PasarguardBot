"""CRUD for Zarinpal top-up payments."""

from __future__ import annotations

import random
import time

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.future import select

from app.db.base import AsyncSessionLocal as Session
from app.db.models.user import User
from app.db.models.zarinpal_payment import ZarinpalPayment
from app.logger import get_logger

logger = get_logger(__name__)

# Only a pending payment may still be verified; everything else is final.
OPEN_STATUSES = ("pending",)
FAILED_STATUSES = ("failed", "canceled", "expired")
# Above the TonPays (11 digits) and crypto order id ranges so direct-pay links never collide.
_ID_MIN = 100_000_000_000
_ID_MAX = 999_999_999_999


class ZarinpalPaymentCRUD:
    async def create(self, *, user_id: int, amount: int, sandbox: bool, source: str) -> ZarinpalPayment:
        last_error: Exception | None = None
        for _ in range(5):
            local_id = random.randint(_ID_MIN, _ID_MAX)
            now = int(time.time())
            try:
                async with Session() as session:
                    payment = ZarinpalPayment(
                        id=local_id,
                        order_id=f"ZP{local_id}",
                        user_id=user_id,
                        amount=amount,
                        sandbox=sandbox,
                        source=source,
                        status="pending",
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(payment)
                    await session.commit()
                    return payment
            except IntegrityError as e:
                last_error = e
        raise ValueError(f"Could not allocate a unique Zarinpal order id: {last_error}")

    async def get(self, local_id: int) -> ZarinpalPayment | None:
        async with Session() as session:
            return (await session.execute(select(ZarinpalPayment).filter_by(id=local_id))).scalar_one_or_none()

    async def get_by_authority(self, authority: str) -> ZarinpalPayment | None:
        async with Session() as session:
            result = await session.execute(select(ZarinpalPayment).filter_by(authority=authority))
            return result.scalars().first()

    async def get_for_user(self, local_id: int, user_id: int) -> ZarinpalPayment | None:
        async with Session() as session:
            result = await session.execute(select(ZarinpalPayment).filter_by(id=local_id, user_id=user_id))
            return result.scalar_one_or_none()

    async def update(self, local_id: int, **fields) -> ZarinpalPayment | None:
        async with Session() as session:
            payment = (await session.execute(select(ZarinpalPayment).filter_by(id=local_id))).scalar_one_or_none()
            if not payment:
                return None
            for key, value in fields.items():
                if hasattr(payment, key):
                    setattr(payment, key, value)
            payment.updated_at = int(time.time())
            await session.commit()
            return payment

    async def close_if_open(self, local_id: int, status: str) -> ZarinpalPayment | None:
        """Move a pending payment to a final status; None when it was already final."""
        async with Session() as session, session.begin():
            payment = (await session.execute(select(ZarinpalPayment).filter_by(id=local_id))).scalar_one_or_none()
            if not payment or payment.status not in OPEN_STATUSES:
                return None
            payment.status = status
            payment.updated_at = int(time.time())
            return payment

    async def delete(self, local_id: int) -> None:
        async with Session() as session:
            payment = (await session.execute(select(ZarinpalPayment).filter_by(id=local_id))).scalar_one_or_none()
            if payment:
                await session.delete(payment)
                await session.commit()

    async def count_open_for_user(self, user_id: int) -> int:
        async with Session() as session:
            result = await session.execute(
                select(func.count())
                .select_from(ZarinpalPayment)
                .where(ZarinpalPayment.user_id == user_id, ZarinpalPayment.status.in_(OPEN_STATUSES))
            )
            return int(result.scalar() or 0)

    async def list_open(self, limit: int = 30) -> list[ZarinpalPayment]:
        """Pending payments, least recently checked first."""
        async with Session() as session:
            result = await session.execute(
                select(ZarinpalPayment)
                .where(ZarinpalPayment.status.in_(OPEN_STATUSES), ZarinpalPayment.authority.isnot(None))
                .order_by(ZarinpalPayment.updated_at.asc())
                .limit(limit)
            )
            return list(result.scalars().all())

    async def list_for_user(self, user_id: int) -> list[ZarinpalPayment]:
        async with Session() as session:
            result = await session.execute(
                select(ZarinpalPayment)
                .where(ZarinpalPayment.user_id == user_id, ZarinpalPayment.authority.isnot(None))
                .order_by(ZarinpalPayment.created_at.desc())
            )
            return list(result.scalars().all())

    async def approve_and_credit(
        self, local_id: int, total_amount: int, *, ref_id: str | None, card_pan: str | None
    ) -> tuple[ZarinpalPayment, int] | None:
        """Mark a pending payment completed and credit the user exactly once."""
        try:
            async with Session() as session, session.begin():
                dialect = session.bind.dialect if session.bind is not None else None
                lock = bool(dialect and dialect.name != "sqlite")
                stmt = select(ZarinpalPayment).where(ZarinpalPayment.id == local_id)
                if lock:
                    stmt = stmt.with_for_update()
                payment = (await session.execute(stmt)).scalar_one_or_none()
                if not payment or payment.status not in OPEN_STATUSES:
                    return None
                user_stmt = select(User).where(User.id == payment.user_id)
                if lock:
                    user_stmt = user_stmt.with_for_update()
                user = (await session.execute(user_stmt)).scalar_one_or_none()
                if not user:
                    return None
                now = int(time.time())
                user.amount = int(user.amount or 0) + int(total_amount)
                payment.status = "completed"
                payment.credited_amount = int(total_amount)
                payment.ref_id = ref_id
                payment.card_pan = card_pan
                payment.paid_at = now
                payment.updated_at = now
                return payment, int(user.amount or 0)
        except SQLAlchemyError as e:
            logger.error("Zarinpal approve_and_credit failed for %s: %s", local_id, e)
            return None


async def zarinpal_stats_since(since: int) -> dict[str, int]:
    """Gateway numbers for the admin dashboard: paid/failed since `since`, plus currently open."""
    async with Session() as session:
        paid = await session.execute(
            select(func.count(), func.coalesce(func.sum(ZarinpalPayment.amount), 0)).where(
                ZarinpalPayment.status == "completed", ZarinpalPayment.paid_at >= since
            )
        )
        paid_count, paid_amount = paid.one()
        open_count = await session.execute(
            select(func.count()).select_from(ZarinpalPayment).where(ZarinpalPayment.status.in_(OPEN_STATUSES))
        )
        failed = await session.execute(
            select(func.count())
            .select_from(ZarinpalPayment)
            .where(ZarinpalPayment.status.in_(FAILED_STATUSES), ZarinpalPayment.updated_at >= since)
        )
        return {
            "paid_today": int(paid_count or 0),
            "amount_today": int(paid_amount or 0),
            "open_invoices": int(open_count.scalar() or 0),
            "failed_today": int(failed.scalar() or 0),
        }
