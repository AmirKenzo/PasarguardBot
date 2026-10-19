"""Unexpected exceptions in WebApp endpoints never reach the user verbatim."""

from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace
from typing import Any

import pytest

from app.routers.webapp import buy, renew
from app.routers.webapp.errors import INTERNAL_ERROR

SECRET = "postgresql://admin:hunter2@db.internal/bot"


@pytest.fixture
def authed(monkeypatch: pytest.MonkeyPatch) -> None:
    async def authenticate_user(**kwargs: Any) -> int:
        return 7

    monkeypatch.setattr(buy, "authenticate_user", authenticate_user)
    monkeypatch.setattr(renew, "authenticate_user", authenticate_user)


def _options_request() -> SimpleNamespace:
    return SimpleNamespace(init_data=None, session_token="t")


def test_unexpected_error_returns_generic_code_and_logs_details(
    authed: None, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    async def boom(self) -> dict:
        raise RuntimeError(SECRET)

    monkeypatch.setattr(buy.WebAppPurchaseService, "get_buy_options", boom)
    with caplog.at_level(logging.ERROR):
        result = asyncio.run(buy.get_buy_options(_options_request()))

    assert result.ok is False
    assert result.error == INTERNAL_ERROR
    assert SECRET not in (result.error or "")
    assert any(SECRET in str(record.exc_info[1]) for record in caplog.records if record.exc_info)


def test_intentional_value_error_message_is_kept(authed: None, monkeypatch: pytest.MonkeyPatch) -> None:
    async def refuse(self) -> dict:
        raise ValueError("فروش در حال حاضر غیرفعال است.")

    monkeypatch.setattr(buy.WebAppPurchaseService, "get_buy_options", refuse)
    result = asyncio.run(buy.get_buy_options(_options_request()))

    assert result.ok is False
    assert result.error == "فروش در حال حاضر غیرفعال است."


def test_auth_value_error_still_reaches_user_where_only_exception_was_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    async def authenticate_user(**kwargs: Any) -> int:
        raise ValueError("نشست منقضی شده است")

    monkeypatch.setattr(renew, "authenticate_user", authenticate_user)
    request = SimpleNamespace(init_data=None, session_token="t", code=1)
    result = asyncio.run(renew.confirm_renew(request))

    assert result.ok is False
    assert result.error == "نشست منقضی شده است"


def test_renew_lookup_crash_is_masked(authed: None, monkeypatch: pytest.MonkeyPatch) -> None:
    async def get_service(self, code: int):
        raise RuntimeError(SECRET)

    monkeypatch.setattr(renew.ServiceCRUD, "get_service", get_service)
    request = SimpleNamespace(init_data=None, session_token="t", code=1)
    result = asyncio.run(renew.confirm_renew(request))

    assert result.error == INTERNAL_ERROR
