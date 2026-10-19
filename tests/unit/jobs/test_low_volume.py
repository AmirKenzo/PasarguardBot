"""Low-volume sweep: notifications, duplicate guard and panel paging cost."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.jobs import registry
from app.jobs.services import low_volume

_GB = 1024**3


def _service(code: int, username: str, *, notified: bool = False, is_test: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        code=code,
        username=username,
        id=1000 + code,
        is_test=is_test,
        expiration_time=0,
        panel_userid=code,
        low_volume_notified=notified,
        in_panel=1,
    )


def _panel_user(username: str, *, limit: int, used: int) -> SimpleNamespace:
    return SimpleNamespace(username=username, data_limit=limit, used_traffic=used)


class _FakeApi:
    def __init__(self, users: list[SimpleNamespace]) -> None:
        self.users = users
        self.calls: list[dict[str, Any]] = []

    async def get_users(self, *, token: str | None, limit: int, offset: int) -> SimpleNamespace:
        self.calls.append({"limit": limit, "offset": offset})
        return SimpleNamespace(users=self.users[offset : offset + limit])

    async def remove_user_by_id(self, *, user_id: int, token: str | None) -> None:
        return None


async def _run(
    monkeypatch: pytest.MonkeyPatch,
    *,
    services: list[SimpleNamespace],
    panel_users: list[SimpleNamespace],
    webhook: bool = False,
) -> tuple[_FakeApi, list[tuple[int, str]], list[tuple[int, dict]]]:
    api = _FakeApi(panel_users)
    sent: list[tuple[int, str]] = []
    updates: list[tuple[int, dict]] = []
    panel = SimpleNamespace(code=1, name="p1", base_url="http://panel", cookie="tok")

    async def fake_panels(self) -> list[SimpleNamespace]:
        return [panel]

    async def fake_batch(self, panel_codes, limit=500, offset=0, *, after_code=None):
        rows = [s for s in services if after_code is None or s.code > after_code]
        return rows[:limit]

    async def fake_update(self, code, **fields):
        updates.append((code, fields))

    async def fake_delete(self, code):
        return True, None

    async def fake_notify(user_id: int, message: str, *, parse_mode: str | None = None) -> bool:
        sent.append((user_id, message))
        return True

    async def fake_text(**kwargs) -> str:
        return "exhausted {service_code} {config_name}"

    async def fake_log(*args, **kwargs) -> None:
        return None

    monkeypatch.setattr(low_volume.PanelsManager, "get_all_panels", fake_panels)
    monkeypatch.setattr(low_volume.ServiceCRUD, "get_all_services_by_panels_batch", fake_batch)
    monkeypatch.setattr(low_volume.ServiceCRUD, "update_service", fake_update)
    monkeypatch.setattr(low_volume.ServiceCRUD, "delete_service", fake_delete)
    monkeypatch.setattr(low_volume, "panel_webhook_notifications_enabled", lambda p: webhook)
    monkeypatch.setattr(low_volume, "PasarguardAPI", lambda base_url: api)
    monkeypatch.setattr(low_volume, "_notify_user", fake_notify)
    monkeypatch.setattr(low_volume, "get_bot_text", fake_text)
    monkeypatch.setattr(low_volume, "send_log_message", fake_log)

    await low_volume.check_low_volume()
    return api, sent, updates


async def test_low_volume_warns_once_and_sets_flag(monkeypatch):
    _, sent, updates = await _run(
        monkeypatch,
        services=[_service(1, "low"), _service(2, "plenty")],
        panel_users=[
            _panel_user("low", limit=10 * _GB, used=10 * _GB - _GB // 2),
            _panel_user("plenty", limit=10 * _GB, used=0),
        ],
    )
    assert [uid for uid, _ in sent] == [1001]
    assert updates == [(1, {"low_volume_notified": True})]


async def test_already_notified_service_is_not_warned_again(monkeypatch):
    _, sent, updates = await _run(
        monkeypatch,
        services=[_service(1, "low", notified=True)],
        panel_users=[_panel_user("low", limit=10 * _GB, used=10 * _GB - _GB // 2)],
    )
    assert sent == []
    assert updates == []


async def test_flag_is_cleared_after_panel_side_top_up(monkeypatch):
    _, sent, updates = await _run(
        monkeypatch,
        services=[_service(1, "topped", notified=True)],
        panel_users=[_panel_user("topped", limit=50 * _GB, used=0)],
    )
    assert sent == []
    assert updates == [(1, {"low_volume_notified": False})]


async def test_unlimited_users_are_never_low_and_their_flag_is_cleared(monkeypatch):
    _, sent, updates = await _run(
        monkeypatch,
        services=[
            _service(1, "unlimited", notified=True),
            _service(2, "unlimited_none"),
            _service(3, "unlimited_test", is_test=True),
        ],
        panel_users=[
            _panel_user("unlimited", limit=0, used=50 * _GB),
            SimpleNamespace(username="unlimited_none", data_limit=None, used_traffic=50 * _GB),
            _panel_user("unlimited_test", limit=0, used=50 * _GB),
        ],
    )
    # No warning, no "exhausted" message and no test-config deletion notice.
    assert sent == []
    assert updates == [(1, {"low_volume_notified": False})]


async def test_exhausted_service_gets_exhausted_message(monkeypatch):
    _, sent, updates = await _run(
        monkeypatch,
        services=[_service(7, "done")],
        panel_users=[_panel_user("done", limit=5 * _GB, used=5 * _GB)],
    )
    assert sent == [(1007, "exhausted 7 done")]
    assert updates == [(7, {"low_volume_notified": True})]


async def test_webhook_panels_are_skipped(monkeypatch):
    api, sent, _ = await _run(
        monkeypatch,
        services=[_service(1, "low")],
        panel_users=[_panel_user("low", limit=10 * _GB, used=10 * _GB)],
        webhook=True,
    )
    assert api.calls == []
    assert sent == []


async def test_paging_uses_large_pages_and_stops_on_short_page(monkeypatch):
    # A bot service missing from the panel must not cause an extra empty request.
    panel_users = [_panel_user(f"u{i}", limit=10 * _GB, used=0) for i in range(low_volume._PAGE_SIZE + 10)]
    api, _, _ = await _run(
        monkeypatch,
        services=[_service(1, "u0"), _service(2, "gone-from-panel")],
        panel_users=panel_users,
    )
    assert api.calls == [
        {"limit": low_volume._PAGE_SIZE, "offset": 0},
        {"limit": low_volume._PAGE_SIZE, "offset": low_volume._PAGE_SIZE},
    ]


async def test_paging_stops_once_every_bot_username_is_found(monkeypatch):
    panel_users = [_panel_user(f"u{i}", limit=10 * _GB, used=0) for i in range(low_volume._PAGE_SIZE * 3)]
    api, _, _ = await _run(monkeypatch, services=[_service(1, "u0")], panel_users=panel_users)
    assert len(api.calls) == 1


def test_job_runs_every_minute(monkeypatch):
    added: dict[str, dict] = {}

    def fake_add_job(func, trigger, **kwargs):
        added[kwargs["id"]] = kwargs

    monkeypatch.setattr(registry, "_JOBS_REGISTERED", False)
    monkeypatch.setattr(registry.scheduler, "add_job", fake_add_job)
    monkeypatch.setattr("app.jobs.backup.register_backup_job_placeholder", lambda: None)
    registry.register_all_jobs()

    job = added["check_low_volume"]
    assert job["seconds"] == 60
    assert job["max_instances"] == 1
    assert job["coalesce"] is True
