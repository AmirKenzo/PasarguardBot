import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.db.crud.bot_reseller import UsageResult
from app.services.bot_reseller import core
from app.telegram.state.keys import build_lock_key
from tests.unit.services.bot_reseller.test_locking import lease_env as lease_env


@pytest.fixture
def creation_env(monkeypatch, lease_env):
    reseller = SimpleNamespace(
        id=1, telegram_id=42, status="active", username_prefix="rb", username_suffix="", mutation_generation=0
    )
    service = SimpleNamespace(
        id=5, panel_code=2, group_ids="[]", price_per_gb=2800, max_users=0, max_user_gb=0, max_user_days=0, name="VIP"
    )
    grant = SimpleNamespace(
        id=9,
        reseller_id=1,
        service_id=5,
        status="approved",
        price_per_gb=None,
        max_users=None,
        max_user_gb=None,
        max_user_days=None,
    )
    panel = SimpleNamespace(code=2)
    env = SimpleNamespace(
        reseller=reseller,
        grant=grant,
        rows=[],
        remote=set(),
        pause_create=False,
        pause_decide=False,
        pause_insert=False,
        fail_insert=False,
        cancel_insert=False,
        cleanup_fail=False,
        withdraw=None,
        lease_env=lease_env,
        create_entered=asyncio.Event(),
        create_resume=asyncio.Event(),
        decide_entered=asyncio.Event(),
        decide_resume=asyncio.Event(),
        insert_entered=asyncio.Event(),
        insert_resume=asyncio.Event(),
    )

    class CRUD:
        async def advance_mutation_generation(self, uid):
            assert uid == reseller.telegram_id
            reseller.mutation_generation += 1
            return True

        async def get_reseller_by_user(self, uid):
            return reseller

        async def get_reseller(self, rid):
            return reseller

        async def list_grants(self, **kwargs):
            return [grant]

        async def get_grant(self, gid):
            return grant

        async def get_services(self, ids):
            return {5: service}

        async def get_service(self, sid):
            return service

        async def balances(self, ids):
            return {42: 3000}

        async def count_users(self, rid):
            return {5: len([row for row in env.rows if row.deleted_at is None])}

        async def list_users(self, rid, **kwargs):
            return [row for row in env.rows if row.deleted_at is None]

        async def decide_grant(self, gid, **values):
            env.decide_entered.set()
            if env.pause_decide:
                await env.decide_resume.wait()
            grant.status = values["status"]
            return grant

        async def add_user(self, *, expected_generation, **values):
            env.insert_entered.set()
            if env.pause_insert:
                await env.insert_resume.wait()
            if (
                expected_generation != reseller.mutation_generation
                or reseller.status != "active"
                or grant.status != "approved"
            ):
                return None
            if env.cancel_insert:
                raise asyncio.CancelledError
            if env.fail_insert:
                return None
            row = SimpleNamespace(id=7, deleted_at=None, observation_revision=0, **values)
            env.rows.append(row)
            return row

        async def apply_usage(self, *args, **kwargs):
            return UsageResult(ok=True)

        async def update_user(self, uid, **values):
            for key, value in values.items():
                setattr(env.rows[0], key, value)
            return True

    async def create(panel, payload):
        env.create_entered.set()
        if env.pause_create:
            await env.create_resume.wait()
        env.remote.add(88)
        if env.withdraw == "grant":
            grant.status = "revoked"
        elif env.withdraw == "suspension":
            reseller.status = "suspended"
        elif env.withdraw == "lease":
            lease_env.redis.values[build_lock_key(42, "bot_reseller")] = "successor"
        return SimpleNamespace(id=88, counter=0)

    async def remove(panel, uid):
        if env.cleanup_fail:
            raise RuntimeError("cleanup failed")
        env.remote.discard(uid)

    monkeypatch.setattr(core, "BotResellerCRUD", CRUD)
    monkeypatch.setattr(core, "_panel", AsyncMock(return_value=panel))
    monkeypatch.setattr(core.panel_api, "create_user", create)
    monkeypatch.setattr(core.panel_api, "remove_user", remove)
    monkeypatch.setattr(core.panel_api, "get_user", AsyncMock(return_value=SimpleNamespace(counter=0)))
    monkeypatch.setattr(core.panel_api, "traffic_counter", lambda user: user.counter)
    monkeypatch.setattr(core.panel_api, "subscription_url", lambda panel, user: "subscription")
    monkeypatch.setattr(core.notify, "notify_reseller", AsyncMock())
    return env


async def _create():
    return await core.create_user(await core.load_context(42), service_id=5, name="ali", gb=1, days=1, note=None)


async def test_create_first_revoke_busy_then_retry_removes_created_user(creation_env):
    env = creation_env
    env.pause_create = True
    task = asyncio.create_task(core.run_mutation(42, _create))
    await env.create_entered.wait()
    with pytest.raises(core.Refused):
        await core.run_mutation(42, lambda: core.revoke_grant(9, actor_id=77))
    env.create_resume.set()
    await task
    assert env.remote == {88}
    assert await core.run_mutation(42, lambda: core.revoke_grant(9, actor_id=77)) == 1
    assert env.grant.status == "revoked"
    assert env.remote == set()
    assert all(row.deleted_at is not None for row in env.rows)


async def test_revoke_first_later_creation_loads_revoked_grant_and_refuses(creation_env):
    env = creation_env
    env.pause_decide = True
    task = asyncio.create_task(core.run_mutation(42, lambda: core.revoke_grant(9, actor_id=77)))
    await env.decide_entered.wait()
    with pytest.raises(core.Refused):
        await core.run_mutation(42, _create)
    env.decide_resume.set()
    await task
    with pytest.raises(core.Refused):
        await core.run_mutation(42, _create)
    assert env.grant.status == "revoked"
    assert env.remote == set()
    assert env.rows == []


@pytest.mark.parametrize("withdraw", ["grant", "suspension", "lease"])
async def test_permission_or_lease_loss_after_remote_create_compensates(creation_env, withdraw):
    env = creation_env
    env.withdraw = withdraw
    with pytest.raises(core.Refused):
        await core.run_mutation(42, _create)
    assert env.remote == set()
    assert env.rows == []
    if withdraw == "lease":
        assert env.lease_env.redis.values[build_lock_key(42, "bot_reseller")] == "successor"


async def test_insert_refusal_removes_known_remote_user(creation_env):
    env = creation_env
    env.fail_insert = True
    with pytest.raises(core.Refused):
        await core.run_mutation(42, _create)
    assert env.rows == []
    assert env.remote == set()


async def test_cancelled_insert_with_no_committed_row_compensates_and_preserves_cancellation(creation_env):
    env = creation_env
    env.cancel_insert = True
    with pytest.raises(asyncio.CancelledError):
        await core.run_mutation(42, _create)
    assert env.rows == []
    assert env.remote == set()


async def test_external_cancellation_during_insert_does_not_remove_committed_user(creation_env):
    env = creation_env
    env.pause_insert = True
    task = asyncio.create_task(core.run_mutation(42, _create))
    await env.insert_entered.wait()
    task.cancel()
    env.insert_resume.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert len(env.rows) == 1
    assert env.rows[0].deleted_at is None
    assert env.remote == {88}


async def test_cleanup_failure_is_reported_without_false_success(creation_env, caplog):
    env = creation_env
    env.fail_insert = env.cleanup_fail = True
    with pytest.raises(core.Refused):
        await core.run_mutation(42, _create)
    assert env.rows == []
    assert env.remote == {88}
    assert "orphan cleanup failed" in caplog.text


async def test_lease_loss_during_insert_cannot_leave_user_after_completed_revocation(monkeypatch, creation_env):
    env = creation_env
    env.pause_insert = True
    lost = asyncio.Event()
    original = core.ResellerMutationLease.ensure_owned

    async def ensure(lease):
        try:
            await original(lease)
        except core.MutationLockUnavailable:
            lost.set()
            raise

    monkeypatch.setattr(core.ResellerMutationLease, "ensure_owned", ensure)
    create = asyncio.create_task(core.run_mutation(42, _create))
    await env.insert_entered.wait()
    await env.lease_env.sleeping.wait()
    env.lease_env.redis.now = 121
    env.lease_env.ticks.put_nowait(None)
    await lost.wait()
    assert await core.run_mutation(42, lambda: core.revoke_grant(9, actor_id=77)) == 0
    assert env.grant.status == "revoked"
    env.insert_resume.set()
    with pytest.raises(core.Refused):
        await create
    assert env.remote == set()
    assert all(row.deleted_at is not None for row in env.rows)
