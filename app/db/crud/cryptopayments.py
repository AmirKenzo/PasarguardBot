import secrets
from collections.abc import Awaitable, Callable, Iterable
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import Float, cast, delete, func, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.future import select

from app.db.base import AsyncSessionLocal as Session
from app.db.models.cryptopayments import CryptoPayments
from app.db.models.user import User
from app.logger import get_logger

logger = get_logger(__name__)

# Jobs accept a transfer within this distance of the invoice amount, so two pending
# invoices of one network must stay further apart than this to be told apart.
AMOUNT_MATCH_TOLERANCE = Decimal("0.000001")
UNIQUE_AMOUNT_ATTEMPTS = 8

AmountPicker = Callable[[set[str]], Awaitable[float]]


class CryptoPaymentsCRUD:
    """CRUD operations for CryptoPayments"""

    async def get_pending_by_arz(self, arz: str):
        try:
            async with Session() as session:
                result = await session.execute(
                    select(CryptoPayments).filter(CryptoPayments.status == "Pending", CryptoPayments.arz == arz.upper())
                )
                return result.scalars().all()
        except SQLAlchemyError:
            return []

    async def update_payment_status(self, order_id: int, status: str, paytime: int | None = None):
        try:
            async with Session() as session:
                result = await session.execute(select(CryptoPayments).filter(CryptoPayments.order_id == order_id))
                payment = result.scalar_one_or_none()
                if payment:
                    payment.status = status
                    if paytime:
                        payment.paytime = paytime
                    await session.commit()
                    return payment
                return None
        except SQLAlchemyError:
            return None

    async def expire_payment(self, order_id: int) -> bool:
        try:
            async with Session() as session, session.begin():
                result = await session.execute(
                    update(CryptoPayments)
                    .where(CryptoPayments.order_id == order_id, CryptoPayments.status == "Pending")
                    .values(status="Expired")
                    .execution_options(synchronize_session=False)
                )
                return result.rowcount == 1
        except SQLAlchemyError:
            return False

    async def get_used_tx_hashes(self, tx_hashes: Iterable[str]) -> set[str]:
        """Return the given transaction ids that already paid an invoice."""
        candidates = {str(h) for h in tx_hashes if h}
        if not candidates:
            return set()
        try:
            async with Session() as session:
                result = await session.execute(
                    select(CryptoPayments.tx_hash).where(CryptoPayments.tx_hash.in_(candidates))
                )
                return {str(h) for h in result.scalars().all() if h}
        except SQLAlchemyError as e:
            # The unique index on tx_hash still blocks a second credit.
            logger.error("Failed to look up used crypto tx hashes: %s", e)
            return set()

    async def approve_and_credit(
        self,
        order_id: int,
        total_amount: int,
        paytime: int | None = None,
        tx_hash: str | None = None,
    ):
        try:
            async with Session() as session, session.begin():
                payment_stmt = select(CryptoPayments).where(CryptoPayments.order_id == order_id)
                dialect = session.bind.dialect if session.bind is not None else None
                if dialect and dialect.name != "sqlite":
                    payment_stmt = payment_stmt.with_for_update()
                payment = (await session.execute(payment_stmt)).scalar_one_or_none()
                if not payment or payment.status != "Pending":
                    return None

                user_stmt = select(User).where(User.id == payment.user_id)
                if dialect and dialect.name != "sqlite":
                    user_stmt = user_stmt.with_for_update()
                user = (await session.execute(user_stmt)).scalar_one_or_none()
                if not user:
                    return None

                values: dict[str, object] = {"status": "Paid"}
                if paytime:
                    values["paytime"] = paytime
                if tx_hash:
                    values["tx_hash"] = tx_hash
                transition = await session.execute(
                    update(CryptoPayments)
                    .where(CryptoPayments.order_id == order_id, CryptoPayments.status == "Pending")
                    .values(**values)
                    .execution_options(synchronize_session=False)
                )
                if transition.rowcount != 1:
                    return None

                user.amount = int(user.amount or 0) + int(total_amount)
                payment.status = "Paid"
                if paytime:
                    payment.paytime = paytime
                if tx_hash:
                    payment.tx_hash = tx_hash
                return payment, int(user.amount or 0)
        except IntegrityError:
            logger.warning(
                "Crypto tx %s already paid another invoice; order_id=%s left pending",
                tx_hash,
                order_id,
            )
            return None
        except SQLAlchemyError:
            logger.exception("Crypto credit failed in the database: order_id=%s", order_id)
            return None


ORDER_ID_MIN = 55555
ORDER_ID_MAX = 999999


async def allocate_order_id(attempts: int = 20) -> int | None:
    """Pick a random invoice number that no stored invoice (of any status) uses yet."""
    try:
        async with Session() as session:
            for _ in range(attempts):
                order_id = ORDER_ID_MIN + secrets.randbelow(ORDER_ID_MAX - ORDER_ID_MIN + 1)
                taken = await session.execute(
                    select(CryptoPayments.order_id).where(CryptoPayments.order_id == order_id)
                )
                if taken.scalar_one_or_none() is None:
                    return order_id
    except SQLAlchemyError:
        return None
    return None


async def set_order_msg_id(order_id: int, msg_id: int) -> None:
    try:
        async with Session() as session:
            await session.execute(
                update(CryptoPayments).where(CryptoPayments.order_id == order_id).values(msg_id=msg_id)
            )
            await session.commit()
    except SQLAlchemyError:
        return


async def add_order_crypto_payment(order_id, user_id, arz, amount, amount_irt, createtime, msg_id=None):
    try:
        arz_upper = arz.upper() if arz else arz

        async with Session() as session:
            new_record = CryptoPayments(
                order_id=order_id,
                user_id=user_id,
                arz=arz_upper,
                amount=amount,
                amount_irt=amount_irt,
                createtime=createtime,
                msg_id=msg_id,
            )
            session.add(new_record)
            await session.commit()

            return {
                "success": True,
                "message": f"Record added successfully for Order ID {order_id}.",
                "record": {
                    "order_id": order_id,
                    "user_id": user_id,
                    "arz": arz_upper,
                    "amount": amount,
                    "amount_irt": amount_irt,
                    "createtime": createtime,
                    "msg_id": msg_id,
                },
            }
    except SQLAlchemyError as e:
        return {
            "success": False,
            "message": f"Error adding record: {e!s}",
        }


def amounts_collide(left: Any, right: Any) -> bool:
    """True when one transfer could match both amounts (same rule as the payment jobs)."""
    try:
        quantum = Decimal("0.000001")
        a = Decimal(str(left)).quantize(quantum)
        b = Decimal(str(right)).quantize(quantum)
    except InvalidOperation:
        return False
    return abs(a - b) <= AMOUNT_MATCH_TOLERANCE


async def _pending_amounts(arz: str, exclude_order_id: int | None = None) -> set[str]:
    async with Session() as session:
        stmt = select(CryptoPayments.amount).where(CryptoPayments.status == "Pending", CryptoPayments.arz == arz)
        if exclude_order_id is not None:
            stmt = stmt.where(CryptoPayments.order_id != exclude_order_id)
        result = await session.execute(stmt)
        return {str(a) for a in result.scalars().all() if a is not None}


async def _set_pending_amount(order_id: int, amount: str) -> None:
    async with Session() as session, session.begin():
        await session.execute(
            update(CryptoPayments)
            .where(CryptoPayments.order_id == order_id, CryptoPayments.status == "Pending")
            .values(amount=amount)
            .execution_options(synchronize_session=False)
        )


async def _discard_pending_order(order_id: int) -> None:
    try:
        async with Session() as session, session.begin():
            await session.execute(
                delete(CryptoPayments)
                .where(CryptoPayments.order_id == order_id, CryptoPayments.status == "Pending")
                .execution_options(synchronize_session=False)
            )
    except SQLAlchemyError as e:
        logger.error("Failed to discard crypto invoice %s: %s", order_id, e)


async def add_order_with_unique_amount(
    *,
    order_id: int,
    user_id: int,
    arz: str,
    amount_irt: int,
    createtime: int,
    pick_amount: AmountPicker,
    msg_id: int | None = None,
    attempts: int = UNIQUE_AMOUNT_ATTEMPTS,
) -> dict:
    """Store a crypto invoice whose amount no other pending invoice of the same network can match.

    Reading the pending amounts and inserting is not atomic, so the row is written first and the
    other pending rows are read afterwards: of two concurrent invoices that picked the same amount,
    at least the later reader sees the other and picks again. The amount is returned in ``record``.
    """
    arz_upper = (arz or "").upper()
    try:
        amount = await pick_amount(await _pending_amounts(arz_upper))
    except (SQLAlchemyError, ValueError) as e:
        return {"success": False, "message": f"Error picking amount: {e!s}"}

    saved = await add_order_crypto_payment(
        order_id=order_id,
        user_id=user_id,
        arz=arz_upper,
        amount=str(amount),
        amount_irt=amount_irt,
        createtime=createtime,
        msg_id=msg_id,
    )
    if not saved.get("success"):
        return saved

    try:
        for _ in range(attempts):
            others = await _pending_amounts(arz_upper, exclude_order_id=order_id)
            if not any(amounts_collide(amount, other) for other in others):
                saved["record"]["amount"] = amount
                return saved
            amount = await pick_amount(others)
            await _set_pending_amount(order_id, str(amount))
    except (SQLAlchemyError, ValueError) as e:
        logger.error("Unique amount check failed for crypto invoice %s: %s", order_id, e)

    await _discard_pending_order(order_id)
    return {"success": False, "message": f"Could not reserve a unique amount for Order ID {order_id}."}


async def count_pending_orders(user_id: int) -> int:
    try:
        async with Session() as session:
            result = await session.execute(
                select(func.count())
                .select_from(CryptoPayments)
                .where(
                    CryptoPayments.user_id == user_id,
                    CryptoPayments.status == "Pending",
                )
            )
            return result.scalar() or 0
    except SQLAlchemyError:
        return 0


async def get_user_all_crypto_transactions(user_id: int):
    try:
        async with Session() as session:
            result = await session.execute(
                select(CryptoPayments)
                .where(CryptoPayments.user_id == user_id)
                .order_by(CryptoPayments.createtime.desc())
            )
            return result.scalars().all()
    except SQLAlchemyError:
        return []


def _paid_crypto_cond(start_ts: int, end_ts: int | None = None):
    cond = (CryptoPayments.status == "Paid") & (CryptoPayments.paytime >= start_ts)
    if end_ts is not None:
        cond = cond & (CryptoPayments.paytime < end_ts)
    return cond


async def get_crypto_period_breakdown(start_ts: int, end_ts: int | None = None) -> dict:
    """Paid crypto per currency: count, crypto volume, IRT total."""
    try:
        async with Session() as session:
            cond = _paid_crypto_cond(start_ts, end_ts)
            stmt = (
                select(
                    CryptoPayments.arz,
                    func.count().label("count"),
                    func.sum(cast(CryptoPayments.amount, Float)).label("crypto_sum"),
                    func.sum(CryptoPayments.amount_irt).label("amount_irt"),
                )
                .where(cond)
                .group_by(CryptoPayments.arz)
                .order_by(func.sum(CryptoPayments.amount_irt).desc())
            )
            rows = (await session.execute(stmt)).all()
            currencies = []
            total_count = 0
            total_irt = 0
            for row in rows:
                arz = (row.arz or "UNKNOWN").upper()
                count = int(row.count or 0)
                crypto_sum = float(row.crypto_sum or 0)
                amount_irt = int(row.amount_irt or 0)
                total_count += count
                total_irt += amount_irt
                currencies.append(
                    {
                        "arz": arz,
                        "count": count,
                        "crypto_sum": crypto_sum,
                        "amount_irt": amount_irt,
                    }
                )
            return {"count": total_count, "total_amount": total_irt, "currencies": currencies}
    except SQLAlchemyError:
        return {"count": 0, "total_amount": 0, "currencies": []}


async def get_global_crypto_breakdown() -> dict:
    """All-time paid crypto breakdown by currency."""
    try:
        async with Session() as session:
            stmt = (
                select(
                    CryptoPayments.arz,
                    func.count().label("count"),
                    func.sum(cast(CryptoPayments.amount, Float)).label("crypto_sum"),
                    func.sum(CryptoPayments.amount_irt).label("amount_irt"),
                )
                .where(CryptoPayments.status == "Paid")
                .group_by(CryptoPayments.arz)
                .order_by(func.sum(CryptoPayments.amount_irt).desc())
            )
            rows = (await session.execute(stmt)).all()
            currencies = []
            total_count = 0
            total_irt = 0
            for row in rows:
                arz = (row.arz or "UNKNOWN").upper()
                count = int(row.count or 0)
                crypto_sum = float(row.crypto_sum or 0)
                amount_irt = int(row.amount_irt or 0)
                total_count += count
                total_irt += amount_irt
                currencies.append(
                    {
                        "arz": arz,
                        "count": count,
                        "crypto_sum": crypto_sum,
                        "amount_irt": amount_irt,
                    }
                )
            return {"count": total_count, "total_amount": total_irt, "currencies": currencies}
    except SQLAlchemyError:
        return {"count": 0, "total_amount": 0, "currencies": []}
