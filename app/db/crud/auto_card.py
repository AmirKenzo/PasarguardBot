import secrets

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.future import select

from app.db.base import GetDB
from app.db.models.auto_card import AutoCard
from app.logger import get_logger

log = get_logger(__name__)

CODE_MIN = 55555
CODE_MAX = 999999


class CRUDAutoCard:
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

    async def claim_by_amount(self, amount: int):
        """Atomically mark one pending auto-card invoice as claimed."""

        async with GetDB() as db, db.begin():
            stmt = select(AutoCard).where(AutoCard.amount == amount, AutoCard.status.is_(False))
            dialect = db.bind.dialect if db.bind is not None else None
            if dialect and dialect.name != "sqlite":
                stmt = stmt.with_for_update()

            result = await db.execute(stmt)
            auto_card = result.scalar_one_or_none()
            if not auto_card:
                return None

            auto_card.status = True
            await db.flush()
            return auto_card
