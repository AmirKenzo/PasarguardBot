"""Session tokens are renewed only after the request authenticated with them, and logout kills the chain."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.routers as routers_module
from app.routers.webapp import auth as auth_module
from app.routers.webapp.state import mark_session_verified, revoked_tokens as revoked_tokens_state

GOOD = "good-token"
REVOKED = "revoked-token"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(routers_module, "maybe_renew_session_token", lambda token: f"renewed:{token}")

    app = FastAPI()
    app.add_middleware(routers_module.WebAppAuthHeaderMiddleware)

    @app.get("/api/webapp/probe")
    async def probe() -> dict[str, bool]:
        session, _ = auth_module.get_header_auth()
        if session == GOOD:
            mark_session_verified(session)
            return {"ok": True}
        return {"ok": False}

    return TestClient(app)


def test_verified_session_is_renewed(client: TestClient) -> None:
    response = client.get("/api/webapp/probe", headers={"X-Session-Token": GOOD})
    assert response.json() == {"ok": True}
    assert response.headers.get("X-Session-Token") == f"renewed:{GOOD}"


def test_rejected_session_is_not_renewed(client: TestClient) -> None:
    response = client.get("/api/webapp/probe", headers={"X-Session-Token": REVOKED})
    assert response.json() == {"ok": False}
    assert "X-Session-Token" not in response.headers


def test_bearer_header_follows_same_rule(client: TestClient) -> None:
    response = client.get("/api/webapp/probe", headers={"Authorization": f"Bearer {REVOKED}"})
    assert "X-Session-Token" not in response.headers


def test_logout_bumps_session_version(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, Any] = {"bumped": []}

    async def parse(token: str) -> tuple[bool, None, dict[str, int]]:
        return True, None, {"uid": 5, "ver": 3}

    async def get_session_version(self, user_id: int) -> int:
        return 3

    async def bump_session_version(self, user_id: int) -> bool:
        calls["bumped"].append(user_id)
        return True

    monkeypatch.setattr(auth_module, "parse_session_token_async", parse)
    monkeypatch.setattr(auth_module.UserCRUD, "get_session_version", get_session_version)
    monkeypatch.setattr(auth_module.UserCRUD, "bump_session_version", bump_session_version)

    result = asyncio.run(auth_module.logout(SimpleNamespace(session_token="t-logout")))

    assert result.ok is True
    assert calls["bumped"] == [5]
    assert "t-logout" in revoked_tokens_state


def test_logout_with_outdated_token_does_not_log_out_current_sessions(monkeypatch: pytest.MonkeyPatch) -> None:
    bumped: list[int] = []

    async def parse(token: str) -> tuple[bool, None, dict[str, int]]:
        return True, None, {"uid": 5, "ver": 2}

    async def get_session_version(self, user_id: int) -> int:
        return 3

    async def bump_session_version(self, user_id: int) -> bool:
        bumped.append(user_id)
        return True

    monkeypatch.setattr(auth_module, "parse_session_token_async", parse)
    monkeypatch.setattr(auth_module.UserCRUD, "get_session_version", get_session_version)
    monkeypatch.setattr(auth_module.UserCRUD, "bump_session_version", bump_session_version)

    asyncio.run(auth_module.logout(SimpleNamespace(session_token="t-old")))

    assert bumped == []
