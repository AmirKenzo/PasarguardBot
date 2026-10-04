"""CRUD for TonPays top-up invoices."""

from __future__ import annotations

import random
import time

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.future import select

from app.db.base import AsyncSessionLocal as Session
from app.db.models.tonpays_invoice import TonPaysInvoice
from app.db.models.user import User
from app.logger import get_logger

logger = get_logger(__name__)

# Statuses that may still turn into a payment; everything else is final.
OPEN_STATUSES = ("pending", "processing", "need_action")
# Above the crypto order id range (55555–999999) so direct-pay links never collide.
_ID_MIN = 10_000_000_000
_ID_MAX = 99_999_999_999


class TonPaysInvoiceCRUD:
    async def create(self, *, user_id: int, amount: int, mode: str, source: str) -> TonPaysInvoice:
        last_error: Exception | None = None
        for _ in range(5):
            local_id = random.randint(_ID_MIN, _ID_MAX)
            now = int(time.time())
            try:
                async with Session() as session:
                    invoice = TonPaysInvoice(
                        id=local_id,
                        order_id=f"KZ{local_id}",
                        user_id=user_id,
                        amount=amount,
                        mode=mode,
                        source=source,
                        status="pending",
                        receipt_sent=False,
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(invoice)
                    await session.commit()
                    return invoice
            except IntegrityError as e:
                last_error = e
        raise ValueError(f"Could not allocate a unique TonPays order id: {last_error}")

    async def get(self, local_id: int) -> TonPaysInvoice | None:
        async with Session() as session:
            return (await session.execute(select(TonPaysInvoice).filter_by(id=local_id))).scalar_one_or_none()

    async def get_by_invoice_id(self, invoice_id: str) -> TonPaysInvoice | None:
        async with Session() as session:
            result = await session.execute(select(TonPaysInvoice).filter_by(invoice_id=invoice_id))
            return result.scalars().first()

    async def get_for_user(self, local_id: int, user_id: int) -> TonPaysInvoice | None:
        async with Session() as session:
            result = await session.execute(select(TonPaysInvoice).filter_by(id=local_id, user_id=user_id))
            return result.scalar_one_or_none()

    async def update(self, local_id: int, **fields) -> TonPaysInvoice | None:
        async with Session() as session:
            invoice = (await session.execute(select(TonPaysInvoice).filter_by(id=local_id))).scalar_one_or_none()
            if not invoice:
                return None
            for key, value in fields.items():
                if hasattr(invoice, key):
                    setattr(invoice, key, value)
            invoice.updated_at = int(time.time())
            await session.commit()
            return invoice

    async def delete(self, local_id: int) -> None:
        async with Session() as session:
            invoice = (await session.execute(select(TonPaysInvoice).filter_by(id=local_id))).scalar_one_or_none()
            if invoice:
                await session.delete(invoice)
                await session.commit()

    async def count_open_for_user(self, user_id: int) -> int:
        async with Session() as session:
            result = await session.execute(
                select(func.count())
                .select_from(TonPaysInvoice)
                .where(TonPaysInvoice.user_id == user_id, TonPaysInvoice.status.in_(OPEN_STATUSES))
            )
            return int(result.scalar() or 0)

    async def list_open(self, limit: int = 40) -> list[TonPaysInvoice]:
        """Open invoices, least recently checked first, so a rate-limited poller covers all of them."""
        async with Session() as session:
            result = await session.execute(
                select(TonPaysInvoice)
                .where(TonPaysInvoice.status.in_(OPEN_STATUSES), TonPaysInvoice.invoice_id.isnot(None))
                .order_by(TonPaysInvoice.updated_at.asc())
                .limit(limit)
            )
            return list(result.scalars().all())

    async def list_for_user(self, user_id: int) -> list[TonPaysInvoice]:
        async with Session() as session:
            result = await session.execute(
                select(TonPaysInvoice)
                .where(TonPaysInvoice.user_id == user_id, TonPaysInvoice.invoice_id.isnot(None))
                .order_by(TonPaysInvoice.created_at.desc())
            )
            return list(result.scalars().all())

    async def approve_and_credit(self, local_id: int, total_amount: int) -> tuple[TonPaysInvoice, int] | None:
        """Mark an open invoice completed and credit the user exactly once."""
        try:
            async with Session() as session, session.begin():
                dialect = session.bind.dialect if session.bind is not None else None
                lock = bool(dialect and dialect.name != "sqlite")
                stmt = select(TonPaysInvoice).where(TonPaysInvoice.id == local_id)
                if lock:
                    stmt = stmt.with_for_update()
                invoice = (await session.execute(stmt)).scalar_one_or_none()
                if not invoice or invoice.status not in OPEN_STATUSES:
                    return None
                user_stmt = select(User).where(User.id == invoice.user_id)
                if lock:
                    user_stmt = user_stmt.with_for_update()
                user = (await session.execute(user_stmt)).scalar_one_or_none()
                if not user:
                    return None
                now = int(time.time())
                user.amount = int(user.amount or 0) + int(total_amount)
                invoice.status = "completed"
                invoice.credited_amount = int(total_amount)
                invoice.paid_at = now
                invoice.updated_at = now
                return invoice, int(user.amount or 0)
        except SQLAlchemyError as e:
            logger.error("TonPays approve_and_credit failed for %s: %s", local_id, e)
            return None
