"""Panel cookie refresh job: no channel log when there are no panels."""

from __future__ import annotations

from typing import Any

from app.jobs.panels import cleanup


async def test_no_panels_sends_no_channel_log(monkeypatch):
    sent: list[tuple[Any, ...]] = []

    async def fake_panels(self) -> list:
        return []

    async def fake_log(*args: Any, **kwargs: Any) -> None:
        sent.append((args, kwargs))

    monkeypatch.setattr(cleanup.PanelsManager, "get_all_panels", fake_panels)
    monkeypatch.setattr(cleanup, "send_log_message", fake_log)

    await cleanup.get_cookies()

    assert sent == []
