"""Unit tests for moving a panel admin's active users into the bot."""

from types import SimpleNamespace

import pytest

from app.services.panels import admin_transfer
from app.services.panels.admin_transfer import TransferError, TransferJob

PANEL = SimpleNamespace(code=7, name="Main", base_url="https://p", cookie="t", auth_type="password")


def _user(
    uid: int, username: str, status: str = "active", data_limit: int = 10, expire: int | None = 1_900_000_000
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uid,
        username=username,
        status=status,
        data_limit=data_limit,
        used_traffic=1,
        expire=expire,
        created_at=None,
        data_limit_reset_strategy="no_reset",
    )


def _job() -> TransferJob:
    return TransferJob(
        id="j",
        panel_code=7,
        panel_name="Main",
        telegram_id=100,
        source_admin="old",
        target_admin="owner",
        actor_id=1,
        notify=False,
    )


def test_scope_is_all_does_not_treat_true_scope_as_own():
    assert admin_transfer._scope_is_all(True)
    assert admin_transfer._scope_is_all(2)
    assert not admin_transfer._scope_is_all(1)
    assert not admin_transfer._scope_is_all(False)
    assert not admin_transfer._scope_is_all(None)


def test_validate_admins_rejects_same_admin():
    with pytest.raises(TransferError):
        admin_transfer._validate_admins("old", "old")


async def test_execute_moves_only_active_and_reports_each_user(monkeypatch):
    users = [
        _user(1, "a"),
        _user(2, "b"),
        _user(3, "c"),
        _user(4, "d"),
        _user(5, "e", status="on_hold"),
        _user(6, "f", status="limited"),
        _user(7, "g", data_limit=0),
        _user(8, "h", expire=None),
    ]
    fetches = iter([users, [_user(3, "c")]])

    async def fake_fetch(panel, admin_username):
        return next(fetches)

    async def fake_existing(panel_code, usernames):
        return {
            "b": SimpleNamespace(id=100, code=11, username="b"),
            "d": SimpleNamespace(id=999, code=12, username="d"),
        }

    moved_ids: list[list[int]] = []

    async def fake_set_owner(panel, chunk, target):
        moved_ids.append([u.id for u in chunk])
        return {u.id: ("HTTP 403" if u.username == "c" else None) for u in chunk}

    async def fake_create(panel, job, user, taken):
        return 5000 + int(user.id), None

    monkeypatch.setattr(admin_transfer, "fetch_admin_users", fake_fetch)
    monkeypatch.setattr(admin_transfer, "_existing_services", fake_existing)
    monkeypatch.setattr(admin_transfer, "_set_owner_chunk", fake_set_owner)
    monkeypatch.setattr(admin_transfer, "_create_service", fake_create)

    job = _job()
    await admin_transfer._execute(PANEL, job)

    results = {row.username: row.result for row in job.rows}
    assert results == {
        "a": "moved",
        "b": "moved_linked",
        "c": "failed",
        "d": "conflict",
        "g": "unlimited",
        "h": "unlimited",
    }
    assert moved_ids == [[1, 2, 3]]
    assert job.total == 6
    assert job.skipped_inactive == 2
    assert job.processed == 6
    assert job.remaining_active_on_source == 1


async def test_set_owner_chunk_falls_back_to_single_calls(monkeypatch):
    calls: list[str] = []

    class FakeApi:
        async def bulk_set_owner(self, bulk, token=None):
            calls.append("bulk")
            return SimpleNamespace(users=["a"], count=1)

        async def set_owner_by_id(self, uid, target, token=None):
            calls.append(f"single:{uid}")
            if uid == 3:
                raise RuntimeError("boom")

    async def fake_call(panel, operation):
        return await operation(FakeApi(), "t")

    monkeypatch.setattr(admin_transfer, "_call", fake_call)

    outcome = await admin_transfer._set_owner_chunk(PANEL, [_user(1, "a"), _user(2, "b"), _user(3, "c")], "owner")

    assert outcome[1] is None
    assert outcome[2] is None
    assert outcome[3] and "boom" in outcome[3]
    assert calls == ["bulk", "single:2", "single:3"]


async def test_list_transfer_admins_excludes_bot_admin(monkeypatch):
    owner = SimpleNamespace(username="owner", total_users=3, status="active", note=None, telegram_id=None)
    reseller = SimpleNamespace(username="ali", total_users=50, status="active", note="100", telegram_id=None)
    other = SimpleNamespace(username="reza", total_users=80, status="active", note=None, telegram_id=None)

    async def fake_access(panel):
        return "owner"

    async def fake_list(panel, **kwargs):
        return [owner, other, reseller]

    monkeypatch.setattr(admin_transfer, "check_transfer_access", fake_access)
    monkeypatch.setattr(admin_transfer, "list_panel_admins", fake_list)

    current, options = await admin_transfer.list_transfer_admins(PANEL, 100)

    assert current == "owner"
    assert [o.username for o in options] == ["ali", "reza"]
    assert options[0].suggested


async def test_resolve_admins_defaults_target_to_bot_admin(monkeypatch):
    async def fake_access(panel):
        return "owner"

    monkeypatch.setattr(admin_transfer, "check_transfer_access", fake_access)

    assert await admin_transfer._resolve_admins(PANEL, "ali", "") == ("ali", "owner")
    with pytest.raises(TransferError):
        await admin_transfer._resolve_admins(PANEL, "owner", None)


def test_unlimited_reason():
    assert admin_transfer._unlimited_reason(_user(1, "a")) is None
    assert admin_transfer._unlimited_reason(_user(1, "a", data_limit=0)) == "unlimited volume"
    assert admin_transfer._unlimited_reason(_user(1, "a", expire=None)) == "unlimited time"
    assert admin_transfer._unlimited_reason(_user(1, "a", data_limit=0, expire=0)) == "unlimited volume and time"
