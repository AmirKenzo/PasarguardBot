"""Per-GB billing of bot resellers: exact amounts, carried remainders, resets and ownership."""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.db.crud import bot_reseller
from app.db.models.bot_reseller import (
    BotReseller,
    BotResellerGrant,
    BotResellerService,
    BotResellerUsageHourly,
    BotResellerUser,
)
from app.db.models.user import User

MB = 1024 * 1024
VIP, GAMING = 1, 2
PRICES = {VIP: 2800.0, GAMING: 4500.0}
HOUR = 1_800_000_000 - 1_800_000_000 % 3600
WALLET = 58219034


@pytest.fixture(autouse=True)
def db(monkeypatch: pytest.MonkeyPatch, tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'bot_reseller.db'}", poolclass=NullPool)
    tables = [
        User.__table__,
        BotResellerService.__table__,
        BotReseller.__table__,
        BotResellerGrant.__table__,
        BotResellerUser.__table__,
        BotResellerUsageHourly.__table__,
    ]

    async def setup():
        async with engine.begin() as conn:
            await conn.run_sync(User.metadata.create_all, tables=tables)
        return async_sessionmaker(engine, expire_on_commit=False)

    session = asyncio.run(setup())
    monkeypatch.setattr(bot_reseller, "Session", session)
    return session


def _user(reseller_id: int, service_id: int, panel_user_id: int, name: str, baseline_mb: int) -> BotResellerUser:
    return BotResellerUser(
        reseller_id=reseller_id,
        service_id=service_id,
        panel_code=1,
        panel_user_id=panel_user_id,
        username=f"rb{reseller_id}_{name}",
        display_name=name,
        baseline_bytes=baseline_mb * MB,
        created_at=0,
    )


def _seed(session, *, balance: int, carry: float = 0.0) -> dict[str, int]:
    async def go():
        async with session() as s:
            s.add(User(id=WALLET, amount=balance))
            s.add(BotReseller(id=1, telegram_id=WALLET, username_prefix="rb1", carry=carry, created_at=0))
            s.add(BotReseller(id=2, telegram_id=99, username_prefix="rb2", created_at=0))
            users = {
                "ali": _user(1, VIP, 11, "ali", 14540),
                "sara": _user(1, VIP, 12, "sara", 8192),
                "pubg": _user(1, GAMING, 13, "pubg", 2150),
                "other": _user(2, VIP, 14, "x", 0),
            }
            s.add_all(users.values())
            await s.commit()
            return {name: row.id for name, row in users.items()}

    return asyncio.run(go())


def _apply(counters: dict[int, int], *, reseller_id: int = 1):
    return asyncio.run(bot_reseller.BotResellerCRUD().apply_usage(reseller_id, counters, PRICES, now=HOUR + 60))


def _read(session, model, **where):
    async def go():
        async with session() as s:
            return (await s.execute(select(model).filter_by(**where))).scalars().all()

    return asyncio.run(go())


def test_worked_example_matches_the_design(db) -> None:
    ids = _seed(db, balance=314_620, carry=0.4)

    first = _apply({ids["ali"]: 15052 * MB, ids["sara"]: 8492 * MB, ids["pubg"]: 2150 * MB})
    assert (first.charged, first.balance) == (2220, 312_400)
    assert _read(db, BotReseller, id=1)[0].carry == pytest.approx(0.7125)

    second = _apply({ids["ali"]: 15062 * MB, ids["pubg"]: 2153 * MB})
    assert second.charged == 41
    assert _read(db, BotReseller, id=1)[0].carry == pytest.approx(0.239844, abs=1e-6)

    third = _apply({ids["ali"]: 15082 * MB, ids["sara"]: 8592 * MB})
    assert third.charged == 328
    assert _read(db, BotReseller, id=1)[0].carry == pytest.approx(0.364844, abs=1e-6)
    assert _read(db, User, id=WALLET)[0].amount == 312_400 - 41 - 328


def test_same_counters_twice_never_bill_twice(db) -> None:
    ids = _seed(db, balance=10_000)
    assert _apply({ids["ali"]: 15052 * MB}).charged == 1400
    assert _apply({ids["ali"]: 15052 * MB}).charged == 0
    assert _read(db, User, id=WALLET)[0].amount == 8_600


def test_counter_that_went_back_counts_from_zero(db) -> None:
    ids = _seed(db, balance=10_000)
    result = _apply({ids["sara"]: 100 * MB})
    assert result.bytes == 100 * MB
    assert _read(db, BotResellerUser, id=ids["sara"])[0].baseline_bytes == 100 * MB


def test_users_of_another_reseller_are_ignored(db) -> None:
    ids = _seed(db, balance=10_000)
    result = _apply({ids["other"]: 1024 * MB})
    assert (result.charged, result.bytes) == (0, 0)
    assert _read(db, BotResellerUser, id=ids["other"])[0].baseline_bytes == 0


def test_hourly_rows_add_up_per_service(db) -> None:
    ids = _seed(db, balance=10_000)
    _apply({ids["ali"]: (14540 + 512) * MB, ids["pubg"]: (2150 + 1024) * MB})
    _apply({ids["ali"]: (14540 + 1024) * MB})
    rows = {row.service_id: row for row in _read(db, BotResellerUsageHourly, reseller_id=1)}
    assert rows[VIP].bytes == 1024 * MB
    assert rows[VIP].amount == pytest.approx(2800.0)
    assert rows[GAMING].amount == pytest.approx(4500.0)
    assert {row.hour for row in rows.values()} == {HOUR}


def test_wallet_may_go_negative_by_one_run(db) -> None:
    ids = _seed(db, balance=500)
    result = _apply({ids["ali"]: (14540 + 1024) * MB})
    assert result.balance == 500 - 2800
