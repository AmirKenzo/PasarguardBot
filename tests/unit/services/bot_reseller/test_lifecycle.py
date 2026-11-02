from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.bot_reseller import core
from app.services.bot_reseller.panel import bulk_set_enabled as real_bulk_set_enabled


@pytest.fixture
def lifecycle_env(monkeypatch):
    reseller = SimpleNamespace(id=1, telegram_id=42, status="active", frozen_at=None, warned_hours=3)
    users = [
        SimpleNamespace(id=i, panel_code=i, panel_user_id=i + 10, disabled_by=mark)
        for i, mark in [(1, None), (2, None), (3, "reseller")]
    ]
    env = SimpleNamespace(
        reseller=reseller, users=users, balance=3000, calls=[], fail_panel=None, missing_panel=None, save=True
    )

    async def update(rid, **values):
        if env.save:
            for key, value in values.items():
                setattr(reseller, key, value)
        return env.save

    async def mark(ids, value):
        for uid in ids:
            next(user for user in users if user.id == uid).disabled_by = value

    async def panel(self, *, code):
        return None if code == env.missing_panel else SimpleNamespace(code=code)

    async def switch(panel, ids, *, enabled):
        if panel.code == env.fail_panel:
            raise RuntimeError("panel failed")
        env.calls.append((panel.code, ids, enabled))

    env.crud = SimpleNamespace(
        advance_mutation_generation=AsyncMock(return_value=True),
        get_reseller=AsyncMock(side_effect=lambda rid: reseller if rid == 1 else None),
        list_users=AsyncMock(side_effect=lambda rid: list(users)),
        balances=AsyncMock(side_effect=lambda ids: {42: env.balance}),
        update_reseller=update,
        set_disabled_by=mark,
    )
    monkeypatch.setattr(core, "BotResellerCRUD", lambda: env.crud)
    monkeypatch.setattr(core.PanelsManager, "get_panel_by_code", panel)
    monkeypatch.setattr(core.panel_api, "bulk_set_enabled", switch)
    monkeypatch.setattr(core.notify, "notify_reseller", AsyncMock())
    monkeypatch.setattr(core.notify, "log_event", AsyncMock())
    return env


async def test_freeze_suspend_top_up_unsuspend_restores_system_users(lifecycle_env):
    env = lifecycle_env
    await core.freeze(env.reseller, 0)
    await core.suspend(1)
    env.balance = 3000
    assert await core.unsuspend(1) == 2
    assert env.reseller.status == "active"
    assert env.reseller.frozen_at is None
    assert env.reseller.warned_hours is None
    assert [u.disabled_by for u in env.users] == [None, None, "reseller"]


@pytest.mark.parametrize("balance", [0, -1])
async def test_unsuspend_without_credit_converts_admin_marks_to_system(lifecycle_env, balance):
    env = lifecycle_env
    env.reseller.status = "suspended"
    env.users[0].disabled_by = "admin"
    env.users[1].disabled_by = "system"
    env.balance = balance
    assert await core.unsuspend(1) == 0
    assert all(not enabled for _, _, enabled in env.calls)
    assert env.reseller.status == "frozen"
    assert env.reseller.frozen_at is not None
    assert [u.disabled_by for u in env.users] == ["system", "system", "reseller"]


async def test_manual_disabled_users_survive_all_transitions(lifecycle_env):
    env = lifecycle_env
    await core.freeze(env.reseller, 0)
    await core.unfreeze(env.reseller)
    await core.suspend(1)
    await core.unsuspend(1)
    assert env.users[2].disabled_by == "reseller"
    assert all(13 not in ids for _, ids, _ in env.calls)


async def test_positive_unsuspend_restores_both_admin_and_system_markers(lifecycle_env):
    env = lifecycle_env
    env.reseller.status = "suspended"
    env.reseller.frozen_at = 123
    env.users[0].disabled_by = "admin"
    env.users[1].disabled_by = "system"
    assert await core.unsuspend(1) == 2
    assert env.reseller.status == "active"
    assert env.reseller.frozen_at is None
    assert [u.disabled_by for u in env.users] == [None, None, "reseller"]


async def test_suspend_rejects_repeat_and_unknown_reseller(lifecycle_env):
    await core.suspend(1)
    with pytest.raises(core.Refused):
        await core.suspend(1)
    with pytest.raises(core.Refused):
        await core.suspend(999)
    with pytest.raises(core.Refused):
        await core.unsuspend(999)


async def test_unsuspend_panel_failure_keeps_suspension_and_can_retry(lifecycle_env):
    env = lifecycle_env
    env.reseller.status = "suspended"
    env.users[0].disabled_by = env.users[1].disabled_by = "admin"
    env.fail_panel = 2
    with pytest.raises(RuntimeError, match="panel failed"):
        await core.unsuspend(1)
    assert env.reseller.status == "suspended"
    assert [u.disabled_by for u in env.users] == [None, "admin", "reseller"]
    env.fail_panel = None
    assert await core.unsuspend(1) == 1
    assert env.calls == [(1, [11], True), (2, [12], True)]
    assert env.reseller.status == "active"


@pytest.mark.parametrize("balance", [0, 3000])
async def test_unsuspend_refuses_failed_status_save(lifecycle_env, balance):
    env = lifecycle_env
    env.reseller.status = "suspended"
    env.balance, env.save = balance, False
    with pytest.raises(core.Refused):
        await core.unsuspend(1)
    assert env.reseller.status == "suspended"


async def test_unsuspend_missing_panel_keeps_suspension(lifecycle_env):
    env = lifecycle_env
    env.reseller.status = "suspended"
    env.users[0].disabled_by = "admin"
    env.missing_panel = 1
    with pytest.raises(core.Refused):
        await core.unsuspend(1)
    assert env.reseller.status == "suspended"
    assert env.users[0].disabled_by == "admin"


@pytest.mark.parametrize("failure", ["panel", "save"])
async def test_partial_unsuspend_then_zero_balance_retry_disables_previously_restored_users(lifecycle_env, failure):
    env = lifecycle_env
    env.reseller.status = "suspended"
    env.users[0].disabled_by = env.users[1].disabled_by = "admin"
    if failure == "panel":
        env.fail_panel = 2
        with pytest.raises(RuntimeError, match="panel failed"):
            await core.unsuspend(1)
    else:
        env.save = False
        with pytest.raises(core.Refused):
            await core.unsuspend(1)
    assert env.users[0].disabled_by is None
    env.fail_panel, env.balance, env.save = None, 0, True
    assert await core.unsuspend(1) == 0
    assert env.reseller.status == "frozen"
    assert [u.disabled_by for u in env.users] == ["system", "system", "reseller"]
    assert (1, [11], False) in env.calls


async def test_suspend_refuses_when_status_save_fails(lifecycle_env):
    env = lifecycle_env
    env.save = False
    with pytest.raises(core.Refused):
        await core.suspend(1)
    assert env.reseller.status == "active"


@pytest.mark.parametrize("marker", ["admin", "system"])
async def test_partial_panel_batch_enable_is_disabled_on_zero_balance_retry(monkeypatch, lifecycle_env, marker):
    env = lifecycle_env
    env.reseller.status = "suspended"
    env.users[:] = [SimpleNamespace(id=i, panel_code=1, panel_user_id=i, disabled_by=marker) for i in range(1, 502)] + [
        SimpleNamespace(id=999, panel_code=1, panel_user_id=999, disabled_by="reseller")
    ]
    online, touched = set(), set()
    enable_calls = 0

    async def enable(*, bulk, token):
        nonlocal enable_calls
        enable_calls += 1
        if enable_calls == 2:
            raise RuntimeError("second batch failed")
        online.update(bulk.ids)
        touched.update(bulk.ids)

    async def disable(*, bulk, token):
        online.difference_update(bulk.ids)
        touched.update(bulk.ids)

    api = SimpleNamespace(bulk_enable_users=enable, bulk_disable_users=disable)

    async def authenticated(panel, call):
        return await call(api, "test")

    monkeypatch.setattr(core.panel_api, "bulk_set_enabled", real_bulk_set_enabled)
    monkeypatch.setattr(core.panel_api, "_with_auth_retry", authenticated)
    with pytest.raises(RuntimeError, match="second batch failed"):
        await core.unsuspend(1)
    assert len(online) == 500
    assert all(user.disabled_by == marker for user in env.users[:-1])
    env.balance = 0
    assert await core.unsuspend(1) == 0
    assert env.reseller.status == "frozen"
    assert online == set()
    assert all(user.disabled_by == "system" for user in env.users[:-1])
    assert env.users[-1].disabled_by == "reseller"
    assert 999 not in touched


async def test_failed_enable_marker_save_is_disabled_on_zero_balance_retry(monkeypatch, lifecycle_env):
    env = lifecycle_env
    env.reseller.status = "suspended"
    env.users[0].disabled_by = env.users[1].disabled_by = "admin"
    online = set()
    original = env.crud.set_disabled_by

    async def save_marks(ids, value):
        if value is None:
            raise RuntimeError("marker save failed")
        await original(ids, value)

    async def switch(panel, ids, *, enabled):
        if enabled:
            online.update(ids)
        else:
            online.difference_update(ids)

    env.crud.set_disabled_by = save_marks
    monkeypatch.setattr(core.panel_api, "bulk_set_enabled", switch)
    with pytest.raises(RuntimeError, match="marker save failed"):
        await core.unsuspend(1)
    assert online == {11}
    assert env.users[0].disabled_by == "admin"
    env.balance = 0
    assert await core.unsuspend(1) == 0
    assert online == set()
    assert [u.disabled_by for u in env.users] == ["system", "system", "reseller"]
