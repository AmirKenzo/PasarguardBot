"""A referral pair is rewarded once, even when first purchases race."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from sqlalchemy import BigInteger, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

from app.db.crud import referral
from app.db.models.referral import ReferralReward
from app.db.models.user import User

REFERRER = 1
REFERRED = 2
REWARD = 40_000
BONUS = 10_000


@compiles(BigInteger, "sqlite")
def _sqlite_bigint(type_, compiler, **kw) -> str:
    # SQLite only autoincrements an INTEGER primary key, like MySQL does for BIGINT.
    return "INTEGER"


@pytest.fixture
def manager(monkeypatch: pytest.MonkeyPatch, tmp_path) -> referral.ReferralManager:
    # A file database gives each session its own connection, like MySQL.
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'referral.db'}")

    async def setup():
        async with engine.begin() as conn:
            await conn.run_sync(User.metadata.create_all, tables=[User.__table__, ReferralReward.__table__])
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as session:
            session.add_all([User(id=REFERRER, amount=0), User(id=REFERRED, amount=0)])
            await session.commit()
        return maker

    async def settings(self):
        return SimpleNamespace(referral_enabled=True, referral_reward_amount=REWARD, referral_bonus_amount=BONUS)

    monkeypatch.setattr(referral, "Session", asyncio.run(setup()))
    monkeypatch.setattr(referral.ReferralManager, "get_referral_settings", settings)
    return referral.ReferralManager()


async def _state() -> tuple[int, int, int]:
    async with referral.Session() as session:
        rewards = (await session.execute(select(func.count(ReferralReward.id)))).scalar_one()
        referrer = await session.get(User, REFERRER)
        referred = await session.get(User, REFERRED)
        return int(rewards), int(referrer.amount), int(referred.amount)


def test_second_reward_for_same_pair_is_rejected(manager) -> None:
    async def run():
        first = await manager.process_referral_reward(REFERRER, REFERRED)
        second = await manager.process_referral_reward(REFERRER, REFERRED)
        return first, second, await _state()

    first, second, state = asyncio.run(run())
    assert first[0] is True
    assert second == (False, "Referral already processed")
    assert state == (1, REWARD, BONUS)


def test_concurrent_first_purchases_pay_once(manager) -> None:
    async def run():
        results = await asyncio.gather(*(manager.process_referral_reward(REFERRER, REFERRED) for _ in range(5)))
        return results, await _state()

    results, state = asyncio.run(run())
    assert sum(ok for ok, _ in results) == 1
    assert state == (1, REWARD, BONUS)


def test_pair_index_rejects_duplicate_rows(manager) -> None:
    async def run():
        async with referral.Session() as session:
            for _ in range(2):
                session.add(
                    ReferralReward(
                        referrer_id=REFERRER,
                        referred_id=REFERRED,
                        reward_amount=REWARD,
                        bonus_amount=BONUS,
                        created_at=0,
                    )
                )
            await session.commit()

    with pytest.raises(referral.IntegrityError):
        asyncio.run(run())
