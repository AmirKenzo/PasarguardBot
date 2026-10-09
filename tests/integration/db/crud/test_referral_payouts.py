"""Referral earnings ledger: cash-outs move each reward once, and paid money never comes back."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from sqlalchemy import BigInteger, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

from app.db.crud import referral, referral_payouts
from app.db.crud.referral_payouts import PAYOUT_CARD, PAYOUT_WALLET, ReferralPayoutCRUD
from app.db.models.referral import ReferralPayout, ReferralReward
from app.db.models.user import User

REFERRER = 1
INVITED = (2, 3, 4)


@compiles(BigInteger, "sqlite")
def _sqlite_bigint(type_, compiler, **kw) -> str:
    # SQLite only autoincrements an INTEGER primary key, like MySQL does for BIGINT.
    return "INTEGER"


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch, tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'payouts.db'}")

    async def setup():
        async with engine.begin() as conn:
            await conn.run_sync(
                User.metadata.create_all,
                tables=[User.__table__, ReferralReward.__table__, ReferralPayout.__table__],
            )
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as session:
            session.add_all([User(id=uid, amount=0) for uid in (REFERRER, *INVITED)])
            await session.commit()
        return maker

    maker = asyncio.run(setup())
    monkeypatch.setattr(referral, "Session", maker)
    monkeypatch.setattr(referral_payouts, "Session", maker)
    return maker


def _earn(settings: SimpleNamespace, rewards: list[int]) -> None:
    async def get_settings(self):
        return settings

    manager = referral.ReferralManager()
    manager.get_referral_settings = get_settings.__get__(manager)

    async def run():
        for invited, amount in zip(INVITED, rewards, strict=False):
            ok, _ = await manager.process_referral_reward(REFERRER, invited, reward_amount=amount, bonus_amount=1_000)
            assert ok

    asyncio.run(run())


def _earnings_settings() -> SimpleNamespace:
    return SimpleNamespace(
        referral_enabled=True,
        referral_reward_amount=0,
        referral_bonus_amount=0,
        referral_reward_destination="earnings",
    )


async def _wallet(maker, user_id: int) -> int:
    async with maker() as session:
        return int((await session.get(User, user_id)).amount)


def test_earnings_stay_out_of_the_wallet(db) -> None:
    _earn(_earnings_settings(), [10_000, 20_000])
    summary = asyncio.run(ReferralPayoutCRUD().earnings_summary(REFERRER))
    assert summary.available == 30_000
    assert asyncio.run(_wallet(db, REFERRER)) == 0
    # The invited users' bonus is still a wallet credit.
    assert asyncio.run(_wallet(db, INVITED[0])) == 1_000


def test_wallet_destination_keeps_the_old_behaviour(db) -> None:
    settings = _earnings_settings()
    settings.referral_reward_destination = "wallet"
    _earn(settings, [10_000])
    assert asyncio.run(_wallet(db, REFERRER)) == 10_000
    assert asyncio.run(ReferralPayoutCRUD().earnings_summary(REFERRER)).available == 0


def test_card_payout_takes_everything_once_and_blocks_a_second_request(db) -> None:
    _earn(_earnings_settings(), [10_000, 20_000])
    crud = ReferralPayoutCRUD()

    payout, error = asyncio.run(crud.cash_out(REFERRER, method=PAYOUT_CARD, min_amount=5_000, card_number="6037" * 4))
    assert error == "" and payout.amount == 30_000
    again, error = asyncio.run(crud.cash_out(REFERRER, method=PAYOUT_CARD, card_number="6037" * 4))
    assert again is None and error
    summary = asyncio.run(crud.earnings_summary(REFERRER))
    assert (summary.available, summary.requested) == (0, 30_000)


def test_minimum_withdrawal_is_enforced(db) -> None:
    _earn(_earnings_settings(), [3_000])
    payout, error = asyncio.run(ReferralPayoutCRUD().cash_out(REFERRER, method=PAYOUT_CARD, min_amount=5_000))
    assert payout is None and "5,000" in error


def test_rejected_payout_returns_to_the_balance_and_paid_never_does(db) -> None:
    _earn(_earnings_settings(), [10_000])
    crud = ReferralPayoutCRUD()

    first, _ = asyncio.run(crud.cash_out(REFERRER, method=PAYOUT_CARD, card_number="6037" * 4))
    rejected, error = asyncio.run(crud.settle(first.id, admin_id=99, paid=False))
    assert error == "" and rejected.status == "rejected"
    assert asyncio.run(crud.earnings_summary(REFERRER)).available == 10_000

    second, _ = asyncio.run(crud.cash_out(REFERRER, method=PAYOUT_CARD, card_number="6037" * 4))
    paid, _ = asyncio.run(crud.settle(second.id, admin_id=99, paid=True))
    assert paid.status == "paid"
    # Settling again (another admin's copy of the message) changes nothing.
    again, error = asyncio.run(crud.settle(second.id, admin_id=98, paid=False))
    assert again.status == "paid" and error
    summary = asyncio.run(crud.earnings_summary(REFERRER))
    assert (summary.available, summary.requested, summary.paid) == (0, 0, 10_000)
    assert asyncio.run(_wallet(db, REFERRER)) == 0


def test_wallet_transfer_credits_once(db) -> None:
    _earn(_earnings_settings(), [10_000, 5_000])
    crud = ReferralPayoutCRUD()

    payout, error = asyncio.run(crud.cash_out(REFERRER, method=PAYOUT_WALLET))
    assert error == "" and payout.status == "completed"
    again, _ = asyncio.run(crud.cash_out(REFERRER, method=PAYOUT_WALLET))
    assert again is None
    assert asyncio.run(_wallet(db, REFERRER)) == 15_000
    assert asyncio.run(crud.earnings_summary(REFERRER)).converted == 15_000

    async def statuses():
        async with db() as session:
            return set((await session.execute(select(ReferralReward.status))).scalars())

    assert asyncio.run(statuses()) == {"converted"}
