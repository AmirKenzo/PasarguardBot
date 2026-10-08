"""The Pasarguard webhook secret is compared in constant time and never logged."""

from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.routers import webhook as webhook_module

SECRET = "s3cr3t-value"


@pytest.mark.parametrize(
    ("received", "expected", "ok"),
    [(SECRET, SECRET, True), ("wrong", SECRET, False), (None, SECRET, False), (SECRET, None, False), ("", "", False)],
)
def test_secret_comparison(received: str | None, expected: str | None, ok: bool) -> None:
    assert webhook_module._is_valid_secret(received, expected) is ok


def _request(secret: str) -> SimpleNamespace:
    async def body() -> bytes:
        return b"[]"

    return SimpleNamespace(headers={"x-webhook-secret": secret, "user-agent": "test"}, body=body)


def test_debug_log_redacts_secret(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    monkeypatch.setattr(webhook_module, "get_webhook_secret", lambda: "other")
    monkeypatch.setattr(webhook_module.logger, "level", logging.DEBUG)
    with caplog.at_level(logging.DEBUG, logger=webhook_module.logger.name), pytest.raises(HTTPException) as exc:
        asyncio.run(webhook_module.handle_webhook(_request(SECRET)))
    assert exc.value.status_code == 403
    assert SECRET not in caplog.text
    assert "user-agent" in caplog.text
