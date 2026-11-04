from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.db.crud.bot_reseller import UsageResult
from app.jobs.reseller import bot_billing as job
from app.services.bot_reseller import locking
from tests.unit.services.bot_reseller.test_lifecycle import lifecycle_env as lifecycle_env
from tests.unit.services.bot_reseller.test_locking import lease_env as lease_env


async def test_delayed_observation_keeps_original_baseline_and_fresh_run_succeeds(monkeypatch):
    entered, resume = asyncio.Event(), asyncio.Event()
    state = {"baseline": 100, "revision": 0, "counter": 150, "balance": 7200, "expected": []}
    reseller = SimpleNamespace(id=1, telegram_id=42, status="active", warned_hours=None)

    class CRUD:
        async def live_users(self):
            return [
                SimpleNamespace(
                    id=7,
                    reseller_id=1,
                    panel_code=2,
                    panel_user_id=8,
                    baseline_bytes=state["baseline"],
                    observation_revision=state["revision"],
                    username="rb_ali",
                )
            ]

        async def list_resellers(self):
            return [reseller]

        async def balances(self, ids):
            return {42: state["balance"]}

        async def apply_usage(self, rid, counters, prices, *, expected_observations=None):
            state["expected"].append(expected_observations)
            if expected_observations != {7: (state["baseline"], state["revision"])}:
                return UsageResult(ok=False)
            charge = counters[7] - state["baseline"]
            state["balance"] -= charge
            state["baseline"] = counters[7]
            state["revision"] += 1
            return UsageResult(ok=True, balance=state["balance"], charged=charge)

    async def fetch(panel, ids):
        entered.set()
        await resume.wait()
        return {8: SimpleNamespace(counter=state["counter"])}, set()

    monkeypatch.setattr(job, "BotResellerCRUD", CRUD)
    monkeypatch.setattr(job.PanelsManager, "get_panel_by_code", AsyncMock(return_value=object()))
    monkeypatch.setattr(job.panel_api, "fetch_users", fetch)
    monkeypatch.setattr(job.panel_api, "traffic_counter", lambda user: user.counter)
    monkeypatch.setattr(job.core, "prices_for", AsyncMock(return_value={1: 1}))
    monkeypatch.setattr(job, "_warn_low_balance", AsyncMock())
    pending = asyncio.create_task(job.run_bot_reseller_billing())
    await entered.wait()
    state["baseline"], state["revision"] = 200, 1
    resume.set()
    await pending
    assert state["expected"] == [{7: (100, 0)}]
    assert state["balance"] == 7200
    assert state["baseline"] == 200
    state["counter"] = 210
    await job.run_bot_reseller_billing()
    assert state["expected"] == [{7: (100, 0)}, {7: (200, 1)}]
    assert state["balance"] == 7190
    assert state["baseline"] == 210


async def test_top_up_after_insufficient_unsuspend_recovers_system_users(monkeypatch, lifecycle_env, lease_env):
    env = lifecycle_env
    env.reseller.status = "suspended"
    env.users[0].disabled_by, env.users[1].disabled_by = "admin", "system"
    env.balance = 0
    assert await job.core.unsuspend(1) == 0
    env.calls.clear()
    env.balance = 3000
    env.crud.list_resellers = AsyncMock(return_value=[env.reseller])
    monkeypatch.setattr(job, "BotResellerCRUD", lambda: env.crud)
    monkeypatch.setattr(job, "_read_counters", AsyncMock(return_value=({}, {})))
    await job.run_bot_reseller_billing()
    assert env.reseller.status == "active"
    assert env.reseller.frozen_at is None
    assert [u.disabled_by for u in env.users] == [None, None, "reseller"]
    assert env.calls == [(1, [11], True), (2, [12], True)]


async def test_top_up_does_not_unfreeze_admin_suspended_reseller(monkeypatch, lifecycle_env):
    env = lifecycle_env
    env.reseller.status = "suspended"
    env.users[0].disabled_by = "admin"
    env.balance = 3000
    env.crud.list_resellers = AsyncMock(return_value=[env.reseller])
    monkeypatch.setattr(job, "BotResellerCRUD", lambda: env.crud)
    monkeypatch.setattr(job, "_read_counters", AsyncMock(return_value=({}, {})))
    await job.run_bot_reseller_billing()
    assert env.reseller.status == "suspended"
    assert env.calls == []
    assert env.users[0].disabled_by == "admin"


@pytest.mark.parametrize("status,balance", [("active", 0), ("frozen", 3000)])
@pytest.mark.parametrize("coordination", ["busy", "unavailable"])
async def test_lifecycle_defers_when_uncoordinated_and_next_run_recovers(
    monkeypatch, lifecycle_env, lease_env, status, balance, coordination, caplog
):
    env = lifecycle_env
    env.reseller.status, env.balance = status, balance
    if status == "frozen":
        env.users[0].disabled_by = env.users[1].disabled_by = "system"
    env.crud.list_resellers = AsyncMock(return_value=[env.reseller])
    env.crud.apply_usage = AsyncMock(return_value=UsageResult(ok=True, balance=balance))
    monkeypatch.setattr(job, "BotResellerCRUD", lambda: env.crud)
    monkeypatch.setattr(job, "_read_counters", AsyncMock(return_value=({1: {7: 100}}, {1: {7: (100, 0)}})))
    monkeypatch.setattr(job.core, "prices_for", AsyncMock(return_value={1: 2800}))
    if coordination == "busy":
        async with locking.reseller_mutation_lock(42):
            await job.run_bot_reseller_billing()
    else:
        lease_env.redis.fail_set = True
        await job.run_bot_reseller_billing()
        lease_env.redis.fail_set = False
    assert env.calls == []
    assert env.reseller.status == status
    assert "errors=1" in caplog.text
    await job.run_bot_reseller_billing()
    assert env.reseller.status == ("frozen" if status == "active" else "active")
    assert len(env.calls) == 2
    assert env.users[2].disabled_by == "reseller"


@pytest.mark.parametrize("status,balance,change", [("active", 0, "topup"), ("frozen", 3000, "suspend")])
async def test_lifecycle_rechecks_status_and_balance_after_acquisition(
    monkeypatch, lifecycle_env, lease_env, status, balance, change, caplog
):
    env = lifecycle_env
    env.reseller.status, env.balance = status, balance
    env.crud.list_resellers = AsyncMock(return_value=[env.reseller])
    env.crud.apply_usage = AsyncMock(return_value=UsageResult(ok=True, balance=balance))
    monkeypatch.setattr(job, "BotResellerCRUD", lambda: env.crud)
    monkeypatch.setattr(job, "_read_counters", AsyncMock(return_value=({1: {7: 100}}, {1: {7: (100, 0)}})))
    monkeypatch.setattr(job.core, "prices_for", AsyncMock(return_value={1: 2800}))
    original = job.core.run_mutation

    async def run(telegram_id, call):
        async def changed():
            if change == "topup":
                env.balance = 3000
            else:
                env.reseller.status = "suspended"
            return await call()

        return await original(telegram_id, changed)

    monkeypatch.setattr(job.core, "run_mutation", run)
    await job.run_bot_reseller_billing()
    assert env.calls == []
    assert env.reseller.status == ("active" if change == "topup" else "suspended")
    assert "frozen=0, unfrozen=0" in caplog.text


async def test_busy_reseller_does_not_block_other_resellers(monkeypatch, lifecycle_env, lease_env):
    env = lifecycle_env
    env.reseller.status = "frozen"
    other = SimpleNamespace(id=2, telegram_id=43, status="frozen")
    env.crud.list_resellers = AsyncMock(return_value=[env.reseller, other])
    env.crud.get_reseller = AsyncMock(side_effect=lambda rid: env.reseller if rid == 1 else other)
    env.crud.balances = AsyncMock(return_value={42: 3000, 43: 3000})
    monkeypatch.setattr(job, "BotResellerCRUD", lambda: env.crud)
    monkeypatch.setattr(job, "_read_counters", AsyncMock(return_value=({}, {})))
    unfreeze = AsyncMock()
    monkeypatch.setattr(job.core, "unfreeze", unfreeze)
    async with locking.reseller_mutation_lock(42):
        await job.run_bot_reseller_billing()
    unfreeze.assert_awaited_once_with(other)


@pytest.mark.parametrize("status,balance", [("active", 0), ("frozen", 3000)])
async def test_failed_lifecycle_save_never_counts_as_completed(
    monkeypatch, lifecycle_env, lease_env, status, balance, caplog
):
    env = lifecycle_env
    env.reseller.status, env.balance, env.save = status, balance, False
    env.crud.list_resellers = AsyncMock(return_value=[env.reseller])
    env.crud.apply_usage = AsyncMock(return_value=UsageResult(ok=True, balance=balance))
    monkeypatch.setattr(job, "BotResellerCRUD", lambda: env.crud)
    monkeypatch.setattr(job, "_read_counters", AsyncMock(return_value=({1: {7: 100}}, {1: {7: (100, 0)}})))
    monkeypatch.setattr(job.core, "prices_for", AsyncMock(return_value={1: 2800}))
    await job.run_bot_reseller_billing()
    assert env.reseller.status == status
    assert "frozen=0, unfrozen=0" in caplog.text
    assert "errors=1" in caplog.text
