"""CRUD for Iranian direct-gateway top-ups (all gateways share one table)."""

from __future__ import annotations

import random
import time

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.future import select

from app.db.base import AsyncSessionLocal as Session
from app.db.models.ir_gateway_payment import IrGatewayPayment
from app.db.models.user import User
from app.logger import get_logger

logger = get_logger(__name__)

# Only a pending payment may still be verified; everything else is final.
OPEN_STATUSES = ("pending",)
FAILED_STATUSES = ("failed", "canceled", "expired")
# Above the TonPays (11 digits) and crypto order id ranges so direct-pay links never collide.
_ID_MIN = 100_000_000_000
_ID_MAX = 999_999_999_999


class IrGatewayPaymentCRUD:
    async def create(
        self, *, gateway: str, order_prefix: str, user_id: int, amount: int, sandbox: bool, source: str
    ) -> IrGatewayPayment:
        last_error: Exception | None = None
        for _ in range(5):
            local_id = random.randint(_ID_MIN, _ID_MAX)
            now = int(time.time())
            try:
                async with Session() as session:
                    payment = IrGatewayPayment(
                        id=local_id,
                        gateway=gateway,
                        order_id=f"{order_prefix}{local_id}",
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
        raise ValueError(f"Could not allocate a unique gateway payment id: {last_error}")

    async def get(self, local_id: int) -> IrGatewayPayment | None:
        async with Session() as session:
            return (await session.execute(select(IrGatewayPayment).filter_by(id=local_id))).scalar_one_or_none()

    async def get_by_authority(self, gateway: str, authority: str) -> IrGatewayPayment | None:
        async with Session() as session:
            result = await session.execute(select(IrGatewayPayment).filter_by(gateway=gateway, authority=authority))
            return result.scalars().first()

    async def get_for_user(self, local_id: int, user_id: int) -> IrGatewayPayment | None:
        async with Session() as session:
            result = await session.execute(select(IrGatewayPayment).filter_by(id=local_id, user_id=user_id))
            return result.scalar_one_or_none()

    async def update(self, local_id: int, **fields) -> IrGatewayPayment | None:
        async with Session() as session:
            payment = (await session.execute(select(IrGatewayPayment).filter_by(id=local_id))).scalar_one_or_none()
            if not payment:
                return None
            for key, value in fields.items():
                if hasattr(payment, key):
                    setattr(payment, key, value)
            payment.updated_at = int(time.time())
            await session.commit()
            return payment

    async def close_if_open(self, local_id: int, status: str) -> IrGatewayPayment | None:
        """Move a pending payment to a final status; None when it was already final."""
        async with Session() as session, session.begin():
            payment = (await session.execute(select(IrGatewayPayment).filter_by(id=local_id))).scalar_one_or_none()
            if not payment or payment.status not in OPEN_STATUSES:
                return None
            payment.status = status
            payment.updated_at = int(time.time())
            return payment

    async def delete(self, local_id: int) -> None:
        async with Session() as session:
            payment = (await session.execute(select(IrGatewayPayment).filter_by(id=local_id))).scalar_one_or_none()
            if payment:
                await session.delete(payment)
                await session.commit()

    async def count_open_for_user(self, user_id: int) -> int:
        """Open payments across every gateway: the cap is per user, not per gateway."""
        async with Session() as session:
            result = await session.execute(
                select(func.count())
                .select_from(IrGatewayPayment)
                .where(IrGatewayPayment.user_id == user_id, IrGatewayPayment.status.in_(OPEN_STATUSES))
            )
            return int(result.scalar() or 0)

    async def list_open(self, limit: int = 30) -> list[IrGatewayPayment]:
        """Pending payments of every gateway, least recently checked first."""
        async with Session() as session:
            result = await session.execute(
                select(IrGatewayPayment)
                .where(IrGatewayPayment.status.in_(OPEN_STATUSES), IrGatewayPayment.authority.isnot(None))
                .order_by(IrGatewayPayment.updated_at.asc())
                .limit(limit)
            )
            return list(result.scalars().all())

    async def list_for_user(self, user_id: int, gateway: str | None = None) -> list[IrGatewayPayment]:
        async with Session() as session:
            stmt = select(IrGatewayPayment).where(
                IrGatewayPayment.user_id == user_id, IrGatewayPayment.authority.isnot(None)
            )
            if gateway:
                stmt = stmt.where(IrGatewayPayment.gateway == gateway)
            result = await session.execute(stmt.order_by(IrGatewayPayment.created_at.desc()))
            return list(result.scalars().all())

    async def approve_and_credit(
        self, local_id: int, total_amount: int, *, ref_id: str | None, card_pan: str | None
    ) -> tuple[IrGatewayPayment, int] | None:
        """Mark a pending payment completed and credit the user exactly once."""
        try:
            async with Session() as session, session.begin():
                dialect = session.bind.dialect if session.bind is not None else None
                lock = bool(dialect and dialect.name != "sqlite")
                stmt = select(IrGatewayPayment).where(IrGatewayPayment.id == local_id)
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
            logger.error("Gateway approve_and_credit failed for %s: %s", local_id, e)
            return None


def _empty_stats() -> dict[str, int]:
    return {"paid_today": 0, "amount_today": 0, "open_payments": 0, "failed_today": 0}


async def ir_gateway_stats_since(since: int) -> dict[str, dict[str, int]]:
    """Per-gateway numbers for the admin panel: paid/failed since `since`, plus currently open."""
    stats: dict[str, dict[str, int]] = {}
    async with Session() as session:
        paid = await session.execute(
            select(IrGatewayPayment.gateway, func.count(), func.coalesce(func.sum(IrGatewayPayment.amount), 0))
            .where(IrGatewayPayment.status == "completed", IrGatewayPayment.paid_at >= since)
            .group_by(IrGatewayPayment.gateway)
        )
        for gateway, count, amount in paid.all():
            row = stats.setdefault(gateway, _empty_stats())
            row["paid_today"], row["amount_today"] = int(count or 0), int(amount or 0)
        open_rows = await session.execute(
            select(IrGatewayPayment.gateway, func.count())
            .where(IrGatewayPayment.status.in_(OPEN_STATUSES))
            .group_by(IrGatewayPayment.gateway)
        )
        for gateway, count in open_rows.all():
            stats.setdefault(gateway, _empty_stats())["open_payments"] = int(count or 0)
        failed = await session.execute(
            select(IrGatewayPayment.gateway, func.count())
            .where(IrGatewayPayment.status.in_(FAILED_STATUSES), IrGatewayPayment.updated_at >= since)
            .group_by(IrGatewayPayment.gateway)
        )
        for gateway, count in failed.all():
            stats.setdefault(gateway, _empty_stats())["failed_today"] = int(count or 0)
    return stats
