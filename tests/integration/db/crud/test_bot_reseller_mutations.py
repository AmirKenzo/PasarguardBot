import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import event, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql.dml import Update

from app.db.crud import bot_reseller
from app.db.models.bot_reseller import BotReseller, BotResellerGrant, BotResellerService, BotResellerUser
from app.services.bot_reseller import core, locking
from tests.integration.db.crud.test_bot_reseller_usage import WALLET, _read, _seed, db as db
from tests.unit.services.bot_reseller.test_locking import FakeRedis


@pytest.fixture
def authorized(db):
    _seed(db, balance=10_000)

    async def setup():
        async with db() as session:
            session.add(BotResellerGrant(reseller_id=1, service_id=1, status="approved", requested_at=0))
            await session.commit()

    asyncio.run(setup())
    return bot_reseller.BotResellerCRUD()


def _insert(crud, generation):
    return asyncio.run(
        crud.add_user(
            expected_generation=generation,
            reseller_id=1,
            service_id=1,
            panel_code=1,
            panel_user_id=999,
            username="rb_new",
            display_name="new",
        )
    )


def test_matching_generation_commits_user_visible_to_successor(db, authorized):
    assert asyncio.run(authorized.advance_mutation_generation(WALLET)) is True
    row = _insert(authorized, 1)
    assert row is not None
    assert asyncio.run(authorized.advance_mutation_generation(WALLET)) is True
    assert _read(db, BotReseller, id=1)[0].mutation_generation == 2
    assert any(user.id == row.id for user in asyncio.run(authorized.list_users(1)))


def test_old_generation_cannot_insert_after_successor_advances(db, authorized):
    assert asyncio.run(authorized.advance_mutation_generation(WALLET)) is True
    assert _insert(authorized, 0) is None
    assert _read(db, BotResellerUser, panel_user_id=999) == []


@pytest.mark.parametrize("denial", ["revoked", "frozen", "suspended"])
def test_current_generation_still_requires_active_authorization(db, authorized, denial):
    async def change():
        async with db() as session:
            if denial == "revoked":
                grant = (await session.execute(select(BotResellerGrant))).scalars().one()
                grant.status = denial
            else:
                reseller = await session.get(BotReseller, 1)
                reseller.status = denial
            await session.commit()

    asyncio.run(change())
    assert _insert(authorized, 0) is None
    assert _read(db, BotResellerUser, panel_user_id=999) == []


def test_generation_advance_missing_reseller_refuses(db, authorized):
    assert asyncio.run(authorized.advance_mutation_generation(99999)) is False
    assert _read(db, BotReseller, id=1)[0].mutation_generation == 0


def test_failed_generation_advance_rolls_back_and_is_retryable(db, authorized):
    engine = db.kw["bind"].sync_engine

    def fail(conn, cursor, statement, parameters, context, executemany):
        if statement.upper().startswith("UPDATE BOT_RESELLERS"):
            raise OperationalError(statement, parameters, RuntimeError("database unavailable"))

    event.listen(engine, "before_cursor_execute", fail)
    try:
        assert asyncio.run(authorized.advance_mutation_generation(WALLET)) is False
    finally:
        event.remove(engine, "before_cursor_execute", fail)
    assert _read(db, BotReseller, id=1)[0].mutation_generation == 0
    assert asyncio.run(authorized.advance_mutation_generation(WALLET)) is True
    assert _read(db, BotReseller, id=1)[0].mutation_generation == 1


def test_successor_waits_for_inflight_insert_before_reading_users(monkeypatch, db, authorized):
    async def go():
        inserted, resume, advancing = asyncio.Event(), asyncio.Event(), asyncio.Event()

        class PausedSession(AsyncSession):
            async def execute(self, statement, *args, **kwargs):
                if isinstance(statement, Update) and "telegram_id" in str(statement.whereclause):
                    advancing.set()
                return await super().execute(statement, *args, **kwargs)

            async def commit(self):
                if any(isinstance(row, BotResellerUser) and row.panel_user_id == 999 for row in self.new):
                    await self.flush()
                    inserted.set()
                    await resume.wait()
                await super().commit()

        monkeypatch.setattr(
            bot_reseller,
            "Session",
            async_sessionmaker(
                db.kw["bind"],
                class_=PausedSession,
                expire_on_commit=False,
            ),
        )
        insert = asyncio.create_task(
            authorized.add_user(
                expected_generation=0,
                reseller_id=1,
                service_id=1,
                panel_code=1,
                panel_user_id=999,
                username="rb_new",
                display_name="new",
            )
        )
        await inserted.wait()

        async def successor():
            assert await authorized.advance_mutation_generation(WALLET)
            return await authorized.list_users(1)

        next_mutation = asyncio.create_task(successor())
        await advancing.wait()
        assert not next_mutation.done()
        resume.set()
        row = await insert
        users = await next_mutation
        assert row is not None
        assert any(user.id == row.id for user in users)

    asyncio.run(go())


def test_stale_pending_rejection_cannot_withdraw_approved_created_user(monkeypatch, db, authorized):
    async def go():
        async with db() as session:
            grant = (await session.execute(select(BotResellerGrant))).scalars().one()
            grant.status = "pending"
            grant_id = grant.id
            session.add(
                BotResellerService(id=1, panel_code=1, name="VIP", price_per_gb=2800, created_at=0, updated_at=0)
            )
            await session.commit()
        entered, resume = asyncio.Event(), asyncio.Event()
        original = bot_reseller.BotResellerCRUD.get_service
        rejection = None

        async def service(crud, sid):
            if asyncio.current_task() is rejection:
                entered.set()
                await resume.wait()
            return await original(crud, sid)

        monkeypatch.setattr(bot_reseller.BotResellerCRUD, "get_service", service)
        monkeypatch.setattr(core.notify, "notify_reseller", AsyncMock())
        monkeypatch.setattr(core.notify, "log_event", AsyncMock())
        monkeypatch.setattr(locking, "get_redis", AsyncMock(return_value=FakeRedis()))
        monkeypatch.setattr(core, "_panel", AsyncMock(return_value=SimpleNamespace(code=1)))
        monkeypatch.setattr(
            core.panel_api, "create_user", AsyncMock(return_value=SimpleNamespace(id=999, used_traffic=0))
        )
        monkeypatch.setattr(core.panel_api, "subscription_url", lambda panel, user: "subscription")
        rejection = asyncio.create_task(core.reject_grant(grant_id, actor_id=88, reason="stale"))
        await entered.wait()
        await core.approve_grant(grant_id, actor_id=77)

        async def create():
            return await core.create_user(
                await core.load_context(WALLET), service_id=1, name="new", gb=1, days=1, note=None
            )

        row, _ = await core.run_mutation(WALLET, create)
        resume.set()
        with pytest.raises(core.Refused):
            await rejection
        current = await authorized.get_grant(grant_id)
        assert current.status == "approved"
        assert current.decided_by == 77
        assert any(user.id == row.id for user in await authorized.list_users(1))

    asyncio.run(go())


def test_pending_rejection_still_commits_its_actor_and_reason(db, authorized):
    async def go():
        async with db() as session:
            grant = (await session.execute(select(BotResellerGrant))).scalars().one()
            grant.status = "pending"
            grant_id = grant.id
            await session.commit()
        rejected = await authorized.decide_grant(grant_id, status="rejected", actor_id=88, reject_reason="reason")
        assert (rejected.status, rejected.decided_by, rejected.reject_reason) == ("rejected", 88, "reason")

    asyncio.run(go())
