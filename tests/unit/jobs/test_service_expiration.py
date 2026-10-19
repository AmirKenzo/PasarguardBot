"""Service expiration job: notices unchanged, flags written in one bulk call per batch."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace

import pytest

from app.jobs.services import expiration

NOW = 1_000_000


def _service(code: int, expiration_time: int, *, is_test: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        code=code,
        username=f"u{code}",
        id=1000 + code,
        is_test=is_test,
        in_panel=1,
        expiration_time=expiration_time,
        expire_notified=False,
        warning=0,
        warning_time=None,
    )


@dataclass
class _Calls:
    sent: list[int] = field(default_factory=list)
    bulk: list[tuple[list[int], dict]] = field(default_factory=list)
    batches: int = 0


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    services: list[SimpleNamespace],
    *,
    page_size: int = 500,
    undeliverable: frozenset[int] = frozenset(),
    log_raises_for: int | None = None,
) -> _Calls:
    calls = _Calls()
    panel = SimpleNamespace(code=1, name="p1")

    async def fake_panels(self) -> list[SimpleNamespace]:
        return [panel]

    async def fake_cleanup_tests() -> int:
        return 0

    async def fake_cleanup_paid(panel_codes, current_time) -> int:
        return 0

    async def fake_batch(self, panel_codes, current_time, expiring_time, limit=500, offset=0, **cursor):
        calls.batches += 1
        after = (cursor.get("after_expiration_time"), cursor.get("after_code"))
        rows = [s for s in services if after[0] is None or (s.expiration_time, s.code) > after]
        return rows[:page_size]

    async def fake_bulk(self, codes, **values) -> int:
        calls.bulk.append((list(codes), values))
        return len(codes)

    async def fake_update(self, code, **values):
        raise AssertionError("per-row update_service must not be used")

    async def fake_notify(user_id: int, message: str, *, parse_mode: str = "html") -> bool:
        if user_id in undeliverable:
            return False
        calls.sent.append(user_id)
        return True

    async def fake_log(*args, **kwargs) -> None:
        if log_raises_for is not None and f"#notification_{log_raises_for}<" in kwargs.get("message", ""):
            raise RuntimeError("log channel down")

    fake_now = SimpleNamespace(timestamp=lambda: NOW)
    monkeypatch.setattr(expiration, "datetime", SimpleNamespace(now=lambda: fake_now))
    monkeypatch.setattr(expiration.PanelsManager, "get_all_panels", fake_panels)
    monkeypatch.setattr(expiration, "cleanup_expired_test_services", fake_cleanup_tests)
    monkeypatch.setattr(expiration, "cleanup_expired_paid_services", fake_cleanup_paid)
    monkeypatch.setattr(expiration, "panel_webhook_notifications_enabled", lambda p: False)
    monkeypatch.setattr(expiration, "panel_expired_auto_delete_enabled", lambda p: True)
    monkeypatch.setattr(expiration, "panel_expired_grace_days", lambda p: 3)
    monkeypatch.setattr(expiration.ServiceCRUD, "get_services_for_expiration_check_batch", fake_batch)
    monkeypatch.setattr(expiration.ServiceCRUD, "update_services_bulk", fake_bulk)
    monkeypatch.setattr(expiration.ServiceCRUD, "update_service", fake_update)
    monkeypatch.setattr(expiration, "_notify_user", fake_notify)
    monkeypatch.setattr(expiration, "send_log_message", fake_log)
    return calls


async def test_flags_written_in_one_bulk_call_per_field_set(monkeypatch):
    services = [
        _service(1, NOW - 100),
        _service(2, NOW - 50),
        _service(5, NOW - 10, is_test=True),  # tests get no grace warning
        _service(3, NOW + 3600),
        _service(4, NOW + 7200),
    ]
    calls = _patch(monkeypatch, services, undeliverable=frozenset({1004}))

    await expiration.handle_service_expiration()

    assert calls.sent == [1001, 1002, 1003]
    assert calls.bulk == [
        ([3], {"expire_notified": True}),
        ([1, 2], {"warning": 1, "warning_time": NOW}),
    ]


async def test_flags_flushed_once_per_batch(monkeypatch):
    services = [_service(code, NOW + 60 * code) for code in range(1, 6)]
    monkeypatch.setattr(expiration, "EXPIRATION_BATCH_SIZE", 2)
    calls = _patch(monkeypatch, services, page_size=2)

    await expiration.handle_service_expiration()

    assert calls.sent == [1001, 1002, 1003, 1004, 1005]
    assert calls.bulk == [
        ([1, 2], {"expire_notified": True}),
        ([3, 4], {"expire_notified": True}),
        ([5], {"expire_notified": True}),
    ]
    assert calls.batches == 3  # last page is short, so no extra empty fetch


async def test_flags_flushed_every_few_sends_within_a_batch(monkeypatch):
    every = expiration._FLAG_FLUSH_EVERY
    count = 2 * every + 3
    services = [_service(code, NOW + 60 * code) for code in range(1, count + 1)]
    calls = _patch(monkeypatch, services)

    await expiration.handle_service_expiration()

    assert len(calls.sent) == count
    assert [len(codes) for codes, _ in calls.bulk] == [every, every, 3]


async def test_sent_flags_are_flushed_when_batch_raises(monkeypatch):
    services = [_service(1, NOW + 60), _service(2, NOW + 120), _service(3, NOW + 180)]
    calls = _patch(monkeypatch, services, log_raises_for=2)

    with pytest.raises(RuntimeError):
        await expiration.handle_service_expiration()

    assert calls.sent == [1001, 1002]
    assert calls.bulk == [([1, 2], {"expire_notified": True})]


async def test_no_bulk_call_when_nothing_delivered(monkeypatch):
    calls = _patch(monkeypatch, [_service(1, NOW + 60)], undeliverable=frozenset({1001}))

    await expiration.handle_service_expiration()

    assert calls.sent == []
    assert calls.bulk == []
