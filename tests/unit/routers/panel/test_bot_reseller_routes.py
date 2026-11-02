from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.routers.panel import bot_resellers as routes
from app.routers.panel.auth import PanelActor


@pytest.mark.parametrize(
    "operation,payload,method",
    [
        ("grant/revoke", {"grant_id": 9}, "revoke_grant"),
        ("suspend", {"id": 1}, "suspend"),
        ("unsuspend", {"id": 1}, "unsuspend"),
        ("users/delete", {"user_id": 7}, "delete_user_by_admin"),
    ],
)
async def test_admin_mutations_lock_target_identity_and_keep_actor_attribution(monkeypatch, operation, payload, method):
    actor = PanelActor(user_id=77, ip="test")
    reseller = SimpleNamespace(id=1, telegram_id=42)
    grant = SimpleNamespace(id=9, reseller_id=1)
    user = SimpleNamespace(id=7, reseller_id=1, deleted_at=None, username="rb_ali")
    crud = SimpleNamespace(
        get_reseller=AsyncMock(return_value=reseller),
        get_grant=AsyncMock(return_value=grant),
        get_user=AsyncMock(return_value=user),
    )
    locks, active, mutations = [], [], []

    async def guard(payload, request, response_model, handle):
        return await handle(actor)

    async def run_mutation(telegram_id, call):
        locks.append(telegram_id)
        active.append(True)
        try:
            return await call()
        finally:
            active.pop()

    async def mutate(*args, **kwargs):
        assert active, "admin mutation ran without target coordination"
        mutations.append((args, kwargs))
        return 1

    audit = AsyncMock()
    monkeypatch.setattr(routes.guard, "run", guard)
    monkeypatch.setattr(routes, "BotResellerCRUD", lambda: crud)
    monkeypatch.setattr(routes.core, "run_mutation", run_mutation, raising=False)
    monkeypatch.setattr(routes.core, method, mutate)
    monkeypatch.setattr(routes, "_audit", audit)
    app = FastAPI()
    app.include_router(routes.router)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/panel/bot-resellers/{operation}", json=payload)
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert locks == [42]
    assert len(mutations) == 1
    assert audit.await_args.args[0].user_id == 77
    if method == "revoke_grant":
        assert mutations[0][1] == {"actor_id": 77}
    if method == "delete_user_by_admin":
        assert crud.get_user.await_count >= 2
        assert crud.get_reseller.await_count >= 2
