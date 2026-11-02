import secrets
import time
from dataclasses import dataclass

from sqlalchemy import func, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.future import select

from app.db.base import GetDB
from app.db.models.auto_card import AutoCard
from app.db.models.transaction import Transaction
from app.db.models.user import User
from app.logger import get_logger
from app.services.billing.payment_bonus import calculate_payment_bonus

log = get_logger(__name__)

CODE_MIN = 55555
CODE_MAX = 999999


@dataclass
class AutoCardPaymentResult:
    invoice: AutoCard
    balance: int
    bonus: int


class CRUDAutoCard:
    async def approve_and_credit(
        self, amount: int, *, bonus_enabled: bool, bonus_percent: int
    ) -> AutoCardPaymentResult | None:
        async with GetDB() as db, db.begin():
            dialect = db.bind.dialect if db.bind is not None else None
            lock = bool(dialect and dialect.name != "sqlite")
            stmt = select(AutoCard).where(AutoCard.amount == amount, AutoCard.status.is_(False))
            invoice = (await db.execute(stmt.with_for_update() if lock else stmt)).scalar_one_or_none()
            if invoice is None:
                return None
            claimed = await db.execute(
                update(AutoCard).where(AutoCard.code == invoice.code, AutoCard.status.is_(False)).values(status=True)
            )
            if claimed.rowcount != 1:
                return None
            stmt = select(User).where(User.id == invoice.id)
            wallet = (await db.execute(stmt.with_for_update() if lock else stmt)).scalar_one_or_none()
            if wallet is None:
                raise LookupError(f"Auto-card wallet not found: {invoice.id}")
            bonus = await calculate_payment_bonus(invoice.first_amount, bonus_enabled, bonus_percent)
            wallet.amount = int(wallet.amount or 0) + invoice.first_amount + bonus
            now = int(time.time())
            db.add(
                Transaction(
                    user_id=invoice.id,
                    amount=invoice.first_amount,
                    method="auto",
                    status="approved",
                    created_at=now,
                    completed_at=now,
                )
            )
            balance = int(wallet.amount)
        return AutoCardPaymentResult(invoice=invoice, balance=balance, bonus=bonus)

    async def create(
        self, code: int, time: int, amount: int, first_amount: int, id: int, status: bool, msg_id: int | None = None
    ):
        async with GetDB() as db:
            auto_card = AutoCard(
                code=code,
                time=int(time),
                amount=amount,
                first_amount=first_amount,
                id=id,
                status=status,
                msg_id=msg_id,
            )
            try:
                db.add(auto_card)
                await db.commit()
                return auto_card
            except SQLAlchemyError as e:
                await db.rollback()
                log.error("Error creating AutoCard: %s", e)
                return None

    async def allocate_code(self, attempts: int = 20) -> int | None:
        """Pick a random invoice code that no stored invoice uses yet."""
        try:
            async with GetDB() as db:
                for _ in range(attempts):
                    code = CODE_MIN + secrets.randbelow(CODE_MAX - CODE_MIN + 1)
                    taken = await db.execute(select(AutoCard.code).where(AutoCard.code == code))
                    if taken.scalar_one_or_none() is None:
                        return code
        except SQLAlchemyError as e:
            log.error("Error allocating AutoCard code: %s", e)
        return None

    async def read(self, code: int):
        async with GetDB() as db:
            result = await db.execute(select(AutoCard).where(AutoCard.code == code))
            return result.scalar_one_or_none()

    async def update(self, code: int, **kwargs):
        async with GetDB() as db:
            result = await db.execute(select(AutoCard).where(AutoCard.code == code))
            auto_card = result.scalar_one_or_none()
            if auto_card:
                for key, value in kwargs.items():
                    setattr(auto_card, key, value)
                await db.commit()
                return auto_card
            return None

    async def delete(self, code: int):
        async with GetDB() as db:
            result = await db.execute(select(AutoCard).where(AutoCard.code == code))
            auto_card = result.scalar_one_or_none()
            if auto_card:
                await db.delete(auto_card)
                await db.commit()
                return True
            return False

    async def get_expired_pending(self, cutoff_ts: int):
        """Return pending auto-card invoices older than cutoff (unix seconds)."""
        async with GetDB() as db:
            result = await db.execute(
                select(AutoCard).where(
                    AutoCard.status.is_(False),
                    AutoCard.time <= int(cutoff_ts),
                )
            )
            return result.scalars().all()

    async def count_pending(self) -> int:
        async with GetDB() as db:
            result = await db.execute(select(func.count()).select_from(AutoCard).where(AutoCard.status.is_(False)))
            return int(result.scalar() or 0)

    async def get_all(self):
        async with GetDB() as db:
            result = await db.execute(select(AutoCard))
            return result.scalars().all()

    async def exists_by_amount(self, amount: int) -> bool:
        async with GetDB() as db:
            result = await db.execute(select(AutoCard).where(AutoCard.amount == amount))
            return result.scalar_one_or_none() is not None

    async def delete_by_amount(self, amount: int) -> bool:
        async with GetDB() as db:
            result = await db.execute(select(AutoCard).where(AutoCard.amount == amount))
            auto_card = result.scalar_one_or_none()
            if auto_card:
                await db.delete(auto_card)
                await db.commit()
                return True
            return False

    async def get_details_by_amount(self, amount: int):
        async with GetDB() as db:
            result = await db.execute(select(AutoCard).where(AutoCard.amount == amount))
            auto_card = result.scalar_one_or_none()
            if auto_card:
                return {"id": auto_card.id, "msg_id": auto_card.msg_id, "code": auto_card.code}
            return None

    async def get_details_or_exists_by_amount(self, amount: int):
        async with GetDB() as db:
            result = await db.execute(select(AutoCard).where(AutoCard.amount == amount))
            auto_card = result.scalar_one_or_none()
            if auto_card:
                return True, auto_card
            return False, "Not Found"
