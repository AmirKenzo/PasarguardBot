import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.bot_reseller import core, locking
from app.telegram.state.keys import build_lock_key


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.expiry = {}
        self.now = 0
        self.fail_set = False
        self.fail_eval = False
        self.fail_release = False
        self.renewed = asyncio.Event()

    async def set(self, key, token, *, nx, ex):
        if self.fail_set:
            raise ConnectionError("unavailable")
        assert nx is True
        assert ex == 120
        if key in self.values and self.expiry[key] > self.now:
            return False
        self.values[key] = token
        self.expiry[key] = self.now + ex
        return True

    async def eval(self, script, numkeys, key, token, *args):
        assert numkeys == 1
        if self.fail_eval or (not args and self.fail_release):
            raise ConnectionError("unavailable")
        if self.expiry.get(key, 0) <= self.now:
            self.values.pop(key, None)
        if self.values.get(key) != token:
            return 0
        if args:
            assert "expire" in script.lower()
            self.expiry[key] = self.now + int(args[0])
            self.renewed.set()
        else:
            assert "del" in script.lower()
            del self.values[key]
        return 1


@pytest.fixture
def lease_env(monkeypatch):
    redis = FakeRedis()
    ticks = asyncio.Queue()
    sleeping = asyncio.Event()

    async def sleep(seconds):
        assert seconds == 30
        sleeping.set()
        await ticks.get()

    monkeypatch.setattr(locking, "get_redis", AsyncMock(return_value=redis))
    monkeypatch.setattr(locking.asyncio, "sleep", sleep)
    return SimpleNamespace(redis=redis, ticks=ticks, sleeping=sleeping)


async def test_contention_rejects_same_reseller_but_not_another(lease_env):
    async with locking.reseller_mutation_lock(42):
        with pytest.raises(locking.MutationBusy):
            async with locking.reseller_mutation_lock(42):
                pytest.fail("contending callback ran")
        async with locking.reseller_mutation_lock(43):
            assert len(lease_env.redis.values) == 2
    assert lease_env.redis.values == {}


@pytest.mark.parametrize("failure", ["missing", "set", "get"])
async def test_unavailable_redis_never_runs_callback(monkeypatch, lease_env, failure):
    if failure == "missing":
        monkeypatch.setattr(locking, "get_redis", AsyncMock(return_value=None))
    elif failure == "get":
        monkeypatch.setattr(locking, "get_redis", AsyncMock(side_effect=ConnectionError("down")))
    else:
        lease_env.redis.fail_set = True
    with pytest.raises(locking.MutationLockUnavailable):
        async with locking.reseller_mutation_lock(42):
            pytest.fail("uncoordinated callback ran")


async def test_stale_owner_never_releases_successor(lease_env):
    key = build_lock_key(42, "bot_reseller")
    with pytest.raises(locking.MutationLockUnavailable):
        async with locking.reseller_mutation_lock(42):
            lease_env.redis.values[key] = "successor"
    assert lease_env.redis.values[key] == "successor"


async def test_exception_releases_owned_lease(lease_env):
    with pytest.raises(ValueError, match="callback failed"):
        async with locking.reseller_mutation_lock(42):
            raise ValueError("callback failed")
    assert lease_env.redis.values == {}


async def test_external_cancellation_preserves_cancellation_and_releases(lease_env):
    entered = asyncio.Event()

    async def operation():
        async with locking.reseller_mutation_lock(42):
            entered.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(operation())
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert lease_env.redis.values == {}


async def test_renewal_retains_ownership_beyond_initial_lifetime(lease_env):
    entered, finish = asyncio.Event(), asyncio.Event()
    key = build_lock_key(42, "bot_reseller")

    async def operation():
        async with locking.reseller_mutation_lock(42):
            entered.set()
            await finish.wait()

    task = asyncio.create_task(operation())
    await entered.wait()
    await lease_env.sleeping.wait()
    token = lease_env.redis.values[key]
    for now in (90, 180):
        lease_env.redis.renewed.clear()
        lease_env.redis.now = now
        lease_env.ticks.put_nowait(None)
        await lease_env.redis.renewed.wait()
        assert lease_env.redis.expiry[key] == now + 120
        assert lease_env.redis.values[key] == token
    finish.set()
    await task
    assert lease_env.redis.values == {}


@pytest.mark.parametrize("failure", ["replacement", "error"])
async def test_renewal_loss_aborts_operation_and_never_reports_success(lease_env, failure):
    entered, cancelled = asyncio.Event(), asyncio.Event()
    key = build_lock_key(42, "bot_reseller")

    async def operation():
        async with locking.reseller_mutation_lock(42):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

    task = asyncio.create_task(operation())
    await entered.wait()
    await lease_env.sleeping.wait()
    if failure == "replacement":
        lease_env.redis.values[key] = "successor"
    else:
        lease_env.redis.fail_eval = True
    lease_env.ticks.put_nowait(None)
    with pytest.raises(locking.MutationLockUnavailable):
        await task
    assert cancelled.is_set()
    if failure == "replacement":
        assert lease_env.redis.values[key] == "successor"


async def test_release_failure_does_not_replay_completed_mutation(lease_env):
    writes = []
    async with locking.reseller_mutation_lock(42):
        writes.append(1)
        lease_env.redis.fail_release = True
    assert writes == [1]
    assert len(lease_env.redis.values) == 1


async def test_core_wrapper_translates_refusals_and_never_runs_busy_callback(monkeypatch, lease_env):
    monkeypatch.setattr(
        core, "BotResellerCRUD", lambda: SimpleNamespace(advance_mutation_generation=AsyncMock(return_value=True))
    )
    callback = AsyncMock(return_value=7)
    assert await core.run_mutation(42, callback) == 7
    async with locking.reseller_mutation_lock(42):
        with pytest.raises(core.Refused):
            await core.run_mutation(42, callback)
    lease_env.redis.fail_set = True
    with pytest.raises(core.Refused):
        await core.run_mutation(42, callback)
    assert callback.await_count == 1


async def test_failed_generation_advance_never_runs_mutation_callback(monkeypatch, lease_env):
    monkeypatch.setattr(
        core, "BotResellerCRUD", lambda: SimpleNamespace(advance_mutation_generation=AsyncMock(return_value=False))
    )
    callback = AsyncMock(return_value=7)
    with pytest.raises(core.Refused):
        await core.run_mutation(42, callback)
    callback.assert_not_awaited()
    assert lease_env.redis.values == {}


async def test_renewal_remains_active_while_cancelled_callback_cleans_up(lease_env):
    entered, cleaning, finish_cleanup = asyncio.Event(), asyncio.Event(), asyncio.Event()
    key = build_lock_key(42, "bot_reseller")

    async def operation():
        async with locking.reseller_mutation_lock(42):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleaning.set()
                await finish_cleanup.wait()

    task = asyncio.create_task(operation())
    await entered.wait()
    await lease_env.sleeping.wait()
    task.cancel()
    await cleaning.wait()
    lease_env.redis.renewed.clear()
    lease_env.redis.now = 90
    lease_env.ticks.put_nowait(None)
    await lease_env.redis.renewed.wait()
    assert lease_env.redis.expiry[key] == 210
    assert not task.done()
    finish_cleanup.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert lease_env.redis.values == {}
