"""Referral earnings kept apart from the wallet, and cashing them out.

A referrer's reward rows *are* the ledger: the withdrawable balance is the sum of
their ``available`` rows, never a stored number that could drift or be bumped
twice. Cashing out moves every available row of the user, in one locked
transaction, onto a payout:

    available ──card──▶ requested ──admin: paid────▶ paid
                            └──────admin: rejected──▶ available (again)
    available ──wallet──▶ converted (credited to the wallet at once)

A row that reached ``paid`` or ``converted`` never comes back, so money that
was paid out cannot be paid out again.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from sqlalchemy import func, select, update
from sqlalchemy.exc import SQLAlchemyError

from app.db.base import AsyncSessionLocal as Session
from app.db.models.referral import ReferralPayout, ReferralReward
from app.db.models.user import User
from app.logger import get_logger

log = get_logger(__name__)

REWARD_AVAILABLE = "available"
REWARD_REQUESTED = "requested"
REWARD_PAID = "paid"
REWARD_CONVERTED = "converted"

PAYOUT_CARD = "card"
PAYOUT_WALLET = "wallet"
PAYOUT_PENDING = "pending"
PAYOUT_PAID = "paid"
PAYOUT_REJECTED = "rejected"
PAYOUT_COMPLETED = "completed"


@dataclass(frozen=True)
class EarningsSummary:
    available: int = 0
    requested: int = 0
    paid: int = 0
    converted: int = 0


class ReferralPayoutCRUD:
    async def earnings_summary(self, user_id: int) -> EarningsSummary:
        """The referrer's earnings by state (rewards sent straight to the wallet are not earnings)."""
        try:
            async with Session() as session:
                rows = (
                    await session.execute(
                        select(ReferralReward.status, func.coalesce(func.sum(ReferralReward.reward_amount), 0))
                        .where(
                            ReferralReward.referrer_id == user_id,
                            ReferralReward.status.in_(
                                (REWARD_AVAILABLE, REWARD_REQUESTED, REWARD_PAID, REWARD_CONVERTED)
                            ),
                        )
                        .group_by(ReferralReward.status)
                    )
                ).all()
        except SQLAlchemyError as e:
            log.error("Error reading referral earnings for %s: %s", user_id, e)
            return EarningsSummary()
        totals = {status: int(total or 0) for status, total in rows}
        return EarningsSummary(
            available=totals.get(REWARD_AVAILABLE, 0),
            requested=totals.get(REWARD_REQUESTED, 0),
            paid=totals.get(REWARD_PAID, 0),
            converted=totals.get(REWARD_CONVERTED, 0),
        )

    async def get_payout(self, payout_id: int) -> ReferralPayout | None:
        try:
            async with Session() as session:
                return await session.get(ReferralPayout, payout_id)
        except SQLAlchemyError as e:
            log.error("Error reading referral payout %s: %s", payout_id, e)
            return None

    async def pending_payout(self, user_id: int) -> ReferralPayout | None:
        try:
            async with Session() as session:
                return (
                    await session.execute(
                        select(ReferralPayout)
                        .where(ReferralPayout.user_id == user_id, ReferralPayout.status == PAYOUT_PENDING)
                        .limit(1)
                    )
                ).scalar_one_or_none()
        except SQLAlchemyError as e:
            log.error("Error reading pending referral payout for %s: %s", user_id, e)
            return None

    async def list_payouts(
        self, *, status: str | None = None, page: int = 1, per_page: int = 25
    ) -> tuple[list[ReferralPayout], int]:
        page = max(int(page), 1)
        per_page = min(max(int(per_page), 1), 100)
        try:
            async with Session() as session:
                where = [ReferralPayout.status == status] if status else []
                total = int(
                    (await session.execute(select(func.count()).select_from(ReferralPayout).where(*where))).scalar()
                    or 0
                )
                rows = (
                    (
                        await session.execute(
                            select(ReferralPayout)
                            .where(*where)
                            .order_by(ReferralPayout.id.desc())
                            .limit(per_page)
                            .offset((page - 1) * per_page)
                        )
                    )
                    .scalars()
                    .all()
                )
                return list(rows), total
        except SQLAlchemyError as e:
            log.error("Error listing referral payouts: %s", e)
            return [], 0

    async def cash_out(
        self,
        user_id: int,
        *,
        method: str,
        min_amount: int = 0,
        card_number: str | None = None,
        card_holder: str | None = None,
    ) -> tuple[ReferralPayout | None, str]:
        """Move all of the user's available earnings onto a new payout.

        ``card`` leaves them ``requested`` until an admin settles it; ``wallet``
        credits the wallet in the same transaction. Returns the payout, or None
        and the reason it was refused.
        """
        if method not in (PAYOUT_CARD, PAYOUT_WALLET):
            return None, "روش برداشت نامعتبر است."
        try:
            async with Session() as session:
                if method == PAYOUT_CARD:
                    open_payout = (
                        await session.execute(
                            select(ReferralPayout.id)
                            .where(ReferralPayout.user_id == user_id, ReferralPayout.status == PAYOUT_PENDING)
                            .limit(1)
                            .with_for_update()
                        )
                    ).scalar_one_or_none()
                    if open_payout is not None:
                        return (
                            None,
                            "یک درخواست برداشت در حال بررسی دارید؛ تا نتیجه‌اش مشخص نشده، درخواست جدید ممکن نیست.",
                        )

                # Locking the rows serialises two taps of the same button: the
                # second one waits, then finds nothing left to move.
                rewards = (
                    await session.execute(
                        select(ReferralReward.id, ReferralReward.reward_amount)
                        .where(ReferralReward.referrer_id == user_id, ReferralReward.status == REWARD_AVAILABLE)
                        .with_for_update()
                    )
                ).all()
                total = sum(int(amount or 0) for _id, amount in rewards)
                if total <= 0:
                    return None, "درآمد قابل برداشتی ندارید."
                if method == PAYOUT_CARD and total < int(min_amount or 0):
                    return None, f"حداقل مبلغ برداشت {int(min_amount):,} تومان است."

                now = int(time.time())
                payout = ReferralPayout(
                    user_id=user_id,
                    amount=total,
                    method=method,
                    status=PAYOUT_PENDING if method == PAYOUT_CARD else PAYOUT_COMPLETED,
                    card_number=card_number,
                    card_holder=card_holder,
                    created_at=now,
                    reviewed_at=None if method == PAYOUT_CARD else now,
                )
                session.add(payout)
                await session.flush()

                ids = [reward_id for reward_id, _amount in rewards]
                moved = await session.execute(
                    update(ReferralReward)
                    .where(ReferralReward.id.in_(ids), ReferralReward.status == REWARD_AVAILABLE)
                    .values(status=REWARD_REQUESTED if method == PAYOUT_CARD else REWARD_CONVERTED, payout_id=payout.id)
                )
                if moved.rowcount != len(ids):
                    await session.rollback()
                    return None, "درآمد شما همزمان در حال تغییر بود؛ دوباره تلاش کنید."
                if method == PAYOUT_WALLET:
                    await session.execute(
                        update(User).where(User.id == user_id).values(amount=func.coalesce(User.amount, 0) + total)
                    )
                await session.commit()
                await session.refresh(payout)
                return payout, ""
        except SQLAlchemyError as e:
            log.error("Error cashing out referral earnings for %s: %s", user_id, e)
            return None, "خطا در ثبت درخواست؛ دوباره تلاش کنید."

    async def settle(
        self, payout_id: int, *, admin_id: int, paid: bool, note: str | None = None
    ) -> tuple[ReferralPayout | None, str]:
        """An admin marks a card payout paid, or rejects it and returns its rewards to the balance."""
        try:
            async with Session() as session:
                payout = (
                    await session.execute(
                        select(ReferralPayout).where(ReferralPayout.id == payout_id).with_for_update()
                    )
                ).scalar_one_or_none()
                if payout is None:
                    return None, "درخواست پیدا نشد."
                if payout.status != PAYOUT_PENDING:
                    return payout, "این درخواست قبلاً بررسی شده است."

                if paid:
                    await session.execute(
                        update(ReferralReward)
                        .where(ReferralReward.payout_id == payout.id, ReferralReward.status == REWARD_REQUESTED)
                        .values(status=REWARD_PAID)
                    )
                else:
                    await session.execute(
                        update(ReferralReward)
                        .where(ReferralReward.payout_id == payout.id, ReferralReward.status == REWARD_REQUESTED)
                        .values(status=REWARD_AVAILABLE, payout_id=None)
                    )
                payout.status = PAYOUT_PAID if paid else PAYOUT_REJECTED
                payout.admin_id = admin_id
                payout.admin_note = note
                payout.reviewed_at = int(time.time())
                await session.commit()
                await session.refresh(payout)
                return payout, ""
        except SQLAlchemyError as e:
            log.error("Error settling referral payout %s: %s", payout_id, e)
            return None, "خطا در ثبت نتیجه؛ دوباره تلاش کنید."
