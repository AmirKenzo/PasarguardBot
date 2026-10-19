"""A failed panel lookup never lets an unverified config name through (WebApp and bot)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import httpx
import pytest

from app.services import webapp_purchase
from app.services.webapp_purchase import USERNAME_CHECK_FAILED, WebAppPurchaseService
from app.telegram.shared.utils import username as username_utils
from app.telegram.shared.utils.username import UsernameLookupError, generate_unique_username, is_username_free

PANEL = SimpleNamespace(code=1, base_url="https://panel.example", cookie="c")


def _status_error(code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://panel.example/api/user/x")
    return httpx.HTTPStatusError("err", request=request, response=httpx.Response(code, request=request))


def _api(behaviour):
    class FakeAPI:
        def __init__(self, base_url: str) -> None:
            pass

        async def get_user_by_username(self, *, username: str, token: str):
            return behaviour(username)

    return FakeAPI


def _raise(exc: Exception):
    def behaviour(username: str):
        raise exc

    return behaviour


@pytest.fixture
def service() -> WebAppPurchaseService:
    return WebAppPurchaseService.__new__(WebAppPurchaseService)


@pytest.mark.parametrize("exc", [httpx.ConnectError("down"), _status_error(500)])
def test_webapp_check_fails_closed(monkeypatch: pytest.MonkeyPatch, service, exc: Exception) -> None:
    monkeypatch.setattr(webapp_purchase, "PasarguardAPI", _api(_raise(exc)))
    assert asyncio.run(service._check_username_available(PANEL, "alice")) == USERNAME_CHECK_FAILED


def test_webapp_check_free_and_taken(monkeypatch: pytest.MonkeyPatch, service) -> None:
    monkeypatch.setattr(webapp_purchase, "PasarguardAPI", _api(_raise(_status_error(404))))
    assert asyncio.run(service._check_username_available(PANEL, "alice")) is None
    monkeypatch.setattr(webapp_purchase, "PasarguardAPI", _api(lambda username: object()))
    assert asyncio.run(service._check_username_available(PANEL, "alice")) is not None


def test_webapp_generate_username_fails_closed(monkeypatch: pytest.MonkeyPatch, service) -> None:
    async def get_panel_by_code(code: int):
        return PANEL

    service.panels = SimpleNamespace(get_panel_by_code=get_panel_by_code)
    monkeypatch.setattr(webapp_purchase, "PasarguardAPI", _api(_raise(httpx.ConnectError("down"))))

    assert asyncio.run(service.generate_username(1)) == {"ok": False, "error": USERNAME_CHECK_FAILED}


@pytest.mark.parametrize("exc", [httpx.ConnectError("down"), _status_error(401)])
def test_bot_lookup_error_raises(monkeypatch: pytest.MonkeyPatch, exc: Exception) -> None:
    monkeypatch.setattr(username_utils, "PasarguardAPI", _api(_raise(exc)))
    with pytest.raises(UsernameLookupError):
        asyncio.run(is_username_free(PANEL, "alice"))
    with pytest.raises(UsernameLookupError):
        asyncio.run(generate_unique_username(PANEL))


def test_bot_free_and_taken(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(username_utils, "PasarguardAPI", _api(_raise(_status_error(404))))
    assert asyncio.run(is_username_free(PANEL, "alice")) is True
    assert asyncio.run(generate_unique_username(PANEL))
    monkeypatch.setattr(username_utils, "PasarguardAPI", _api(lambda username: object()))
    assert asyncio.run(is_username_free(PANEL, "alice")) is False
