"""Users banned in the bot are refused by every Mini App auth path."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from app.routers.webapp import auth as auth_module, state

BANNED = 13
ACTIVE = 14
PHONE = "09120000013"


@pytest.fixture(autouse=True)
def bans(monkeypatch: pytest.MonkeyPatch) -> None:
    state.otp_sessions.clear()
    state.otp_start_history.clear()
    state.otp_failure_history.clear()

    async def is_user_banned(user_id: int) -> bool:
        return int(user_id) == BANNED

    async def parse(token: str):
        return True, None, {"uid": int(token), "ver": 0}

    async def get_session_version(self, user_id: int) -> int:
        return 0

    async def build_payload(user_id: int, **kwargs) -> dict:
        return {"ok": True}

    monkeypatch.setattr(auth_module, "is_user_banned", is_user_banned)
    monkeypatch.setattr(auth_module, "parse_session_token_async", parse)
    monkeypatch.setattr(auth_module, "get_header_auth", lambda: (None, None))
    monkeypatch.setattr(auth_module, "validate_webapp_data", lambda params: (True, None))
    monkeypatch.setattr(auth_module.UserCRUD, "get_session_version", get_session_version)
    monkeypatch.setattr(auth_module, "build_user_payload_no_services", build_payload)


def _init_data(user_id: int) -> str:
    return "user=" + json.dumps({"id": user_id, "first_name": "t"})


@pytest.mark.parametrize("kwargs", [{"session_token": str(BANNED)}, {"init_data": _init_data(BANNED)}])
def test_banned_user_is_rejected(kwargs: dict) -> None:
    with pytest.raises(ValueError, match=auth_module._BANNED_ERROR):
        asyncio.run(auth_module.authenticate_user(**kwargs))


@pytest.mark.parametrize("kwargs", [{"session_token": str(ACTIVE)}, {"init_data": _init_data(ACTIVE)}])
def test_active_user_is_allowed(kwargs: dict) -> None:
    assert asyncio.run(auth_module.authenticate_user(**kwargs)) == ACTIVE


def test_banned_session_info_is_refused() -> None:
    request = SimpleNamespace(headers={}, query_params={})
    result = asyncio.run(auth_module.get_webapp_info_session(request, session_token=str(BANNED)))
    assert result.ok is False
    assert result.error == auth_module._BANNED_ERROR


def test_banned_user_gets_no_otp(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[str] = []

    async def get_user_by_phone(self, phone: str):
        return SimpleNamespace(id=BANNED, number=PHONE)

    async def send_code(user_id: int, code: str) -> None:
        sent.append(code)

    monkeypatch.setattr(auth_module.UserCRUD, "get_user_by_phone", get_user_by_phone)
    monkeypatch.setattr(auth_module, "_send_telegram_code", send_code)
    request = SimpleNamespace(headers={}, client=SimpleNamespace(host="203.0.113.9"))
    result = asyncio.run(auth_module.start_phone_login(SimpleNamespace(phone=PHONE), request))
    assert result.ok is False
    assert sent == []


def test_banned_user_cannot_log_in_with_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    async def get_user_by_api_key_hash(self, key_hash: str):
        return SimpleNamespace(id=BANNED)

    monkeypatch.setattr(auth_module.UserCRUD, "get_user_by_api_key_hash", get_user_by_api_key_hash)
    request = SimpleNamespace(headers={}, client=SimpleNamespace(host="203.0.113.10"))
    result = asyncio.run(auth_module.login_with_api_key(SimpleNamespace(api_key="k"), request))
    assert result.ok is False
    assert result.error == auth_module._BANNED_ERROR
