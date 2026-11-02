from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.routers.webapp import bot_reseller as routes


@pytest.mark.parametrize(
    "operation,payload",
    [
        ("create", {"service_id": 1, "name": "ali"}),
        ("edit", {"id": 7}),
        ("toggle", {"id": 7, "enabled": True}),
        ("revoke", {"id": 7}),
        ("reset", {"id": 7}),
        ("delete", {"id": 7}),
    ],
)
async def test_all_writes_lock_target_and_load_context_inside(monkeypatch, operation, payload):
    active, locks = [], []
    ctx = SimpleNamespace(
        services={1: SimpleNamespace(name="VIP", price_per_gb=2800)},
        terms=lambda sid: SimpleNamespace(price_per_gb=2800),
    )
    row = SimpleNamespace(
        id=7, service_id=1, display_name="ali", username="rb_ali", note=None, disabled_by=None, baseline_bytes=0
    )

    async def run_mutation(telegram_id, call):
        locks.append(telegram_id)
        active.append(True)
        try:
            return await call()
        finally:
            active.pop()

    async def load(telegram_id):
        assert active, "context loaded before coordination"
        assert telegram_id == 42
        return ctx

    monkeypatch.setattr(routes, "authenticate_user", AsyncMock(return_value=42))
    monkeypatch.setattr(routes, "acquire_user_lock", AsyncMock(return_value=True), raising=False)
    monkeypatch.setattr(routes, "release_user_lock", AsyncMock(), raising=False)
    monkeypatch.setattr(routes.core, "run_mutation", run_mutation, raising=False)
    monkeypatch.setattr(routes.core, "load_context", load)
    monkeypatch.setattr(routes.core, "create_user", AsyncMock(return_value=(row, "subscription")))
    for name in ("edit_user", "set_user_enabled", "reset_user_usage", "delete_user"):
        monkeypatch.setattr(routes.core, name, AsyncMock())
    monkeypatch.setattr(routes.core, "revoke_link", AsyncMock(return_value="subscription"))
    app = FastAPI()
    app.include_router(routes.router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/webapp/bot-reseller/user/{operation}", json=payload)
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert locks == [42]


@pytest.mark.parametrize("operation,payload", [("state", {}), ("users", {}), ("user", {"id": 7}), ("usage", {})])
async def test_reads_remain_available_without_mutation_coordination(monkeypatch, operation, payload):
    reseller = SimpleNamespace(id=1, telegram_id=42, status="active", username_prefix="rb", username_suffix="")
    ctx = SimpleNamespace(reseller=reseller, grants=[], services={}, approved=lambda: [], terms=lambda sid: None)
    row = SimpleNamespace(
        id=7, service_id=1, display_name="ali", username="rb_ali", note=None, disabled_by=None, baseline_bytes=0
    )
    crud = SimpleNamespace(
        balances=AsyncMock(return_value={42: 3000}),
        count_users=AsyncMock(return_value={}),
        usage_rows=AsyncMock(return_value=[]),
        list_users=AsyncMock(return_value=[]),
    )
    locks = AsyncMock(side_effect=AssertionError("reads must not lock"))
    monkeypatch.setattr(routes.core, "run_mutation", locks, raising=False)
    monkeypatch.setattr(routes, "authenticate_user", AsyncMock(return_value=42))
    monkeypatch.setattr(routes.core, "load_context", AsyncMock(return_value=ctx))
    monkeypatch.setattr(routes.core, "user_live", AsyncMock(return_value=(row, None, None)))
    monkeypatch.setattr(routes, "BotResellerCRUD", lambda: crud)
    app = FastAPI()
    app.include_router(routes.router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/webapp/bot-reseller/{operation}", json=payload)
    assert response.status_code == 200
    assert response.json()["ok"] is True
    locks.assert_not_awaited()
