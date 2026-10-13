"""Rejected webapp sessions carry ``error_code: session_invalid``; other failures do not."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.routers as routers_module
from app.routers.webapp import auth as auth_module, transactions as transactions_module
from app.routers.webapp.errors import INTERNAL_ERROR, SESSION_INVALID
from app.routers.webapp.state import revoked_tokens

ACTIVE = "1"
BANNED = "2"
EXPIRED = "3"
REVOKED = "revoked-token"
INVALID = "garbage"


@pytest.fixture(autouse=True)
def sessions(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    async def parse(token: str) -> tuple[bool, str | None, dict[str, int] | None]:
        if token == INVALID:
            return False, "توکن نامعتبر است", None
        return True, None, {"uid": int(token), "ver": 0}

    async def get_session_version(self: Any, user_id: int) -> int:
        return 1 if str(user_id) == EXPIRED else 0

    async def is_user_banned(user_id: int) -> bool:
        return str(user_id) == BANNED

    async def build_payload(user_id: int, **kwargs: Any) -> dict[str, Any]:
        return {"ok": True}

    monkeypatch.setattr(routers_module, "maybe_renew_session_token", lambda token: None)
    monkeypatch.setattr(auth_module, "parse_session_token_async", parse)
    monkeypatch.setattr(auth_module.UserCRUD, "get_session_version", get_session_version)
    monkeypatch.setattr(auth_module, "is_user_banned", is_user_banned)
    monkeypatch.setattr(auth_module, "build_user_payload_no_services", build_payload)
    revoked_tokens[REVOKED] = float("inf")
    yield
    revoked_tokens.pop(REVOKED, None)


def _info_session(token: str | None) -> Any:
    request = SimpleNamespace(headers={}, query_params={})
    return asyncio.run(auth_module.get_webapp_info_session(request, session_token=token))


@pytest.mark.parametrize("token", [None, INVALID, EXPIRED, REVOKED])
def test_info_session_rejection_carries_code(token: str | None) -> None:
    result = _info_session(token)
    assert result.ok is False
    assert result.error
    assert result.error_code == SESSION_INVALID


def test_info_session_banned_has_no_code() -> None:
    result = _info_session(BANNED)
    assert result.ok is False
    assert result.error == auth_module._BANNED_ERROR
    assert result.error_code is None


def test_info_session_internal_error_has_no_code(monkeypatch: pytest.MonkeyPatch) -> None:
    async def boom(user_id: int, **kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("db down")

    monkeypatch.setattr(auth_module, "build_user_payload_no_services", boom)
    result = _info_session(ACTIVE)
    assert result.error == INTERNAL_ERROR
    assert result.error_code is None


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.add_middleware(routers_module.WebAppAuthHeaderMiddleware)
    app.include_router(transactions_module.router, prefix="/api")
    return TestClient(app)


def _post_transactions(client: TestClient, token: str | None) -> Any:
    headers = {"X-Session-Token": token} if token else {}
    return client.post("/api/webapp/transactions", json={}, headers=headers)


@pytest.mark.parametrize("token", [None, INVALID, EXPIRED, REVOKED])
def test_protected_route_rejection_carries_code(client: TestClient, token: str | None) -> None:
    response = _post_transactions(client, token)
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["error"]
    assert body["error_code"] == SESSION_INVALID
    assert int(response.headers["content-length"]) == len(response.content)


def test_protected_route_banned_has_no_code(client: TestClient) -> None:
    body = _post_transactions(client, BANNED).json()
    assert body["ok"] is False
    assert body["error"] == auth_module._BANNED_ERROR
    assert "error_code" not in body


def test_protected_route_internal_error_has_no_code(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken_crud() -> None:
        raise RuntimeError("db down")

    monkeypatch.setattr(transactions_module, "TransactionCRUD", broken_crud)
    body = _post_transactions(client, ACTIVE).json()
    assert body["ok"] is False
    assert body["error"] == INTERNAL_ERROR
    assert "error_code" not in body
