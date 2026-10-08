"""Renew locks are only taken for an owner's real service and are dropped once unused."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.routers.webapp import renew as renew_module, state

OWNER = 5
CODE = 900


@pytest.fixture(autouse=True)
def clean_locks() -> None:
    state.renew_confirm_locks.clear()


def _request(code: int = CODE) -> SimpleNamespace:
    return SimpleNamespace(code=code, init_data=None, session_token="t", plan_id=1, discount_code=None)


def test_unauthenticated_request_allocates_no_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    async def reject(**kwargs):
        raise ValueError("bad token")

    monkeypatch.setattr(renew_module, "authenticate_user", reject)
    for code in range(50):
        assert asyncio.run(renew_module.confirm_renew(_request(code))).ok is False
    assert state.renew_confirm_locks == {}


def test_foreign_service_allocates_no_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    async def auth(**kwargs) -> int:
        return OWNER

    async def get_service(self, code: int):
        return True, SimpleNamespace(id=OWNER + 1)

    monkeypatch.setattr(renew_module, "authenticate_user", auth)
    monkeypatch.setattr(renew_module.ServiceCRUD, "get_service", get_service)
    assert asyncio.run(renew_module.confirm_renew(_request())).ok is False
    assert state.renew_confirm_locks == {}


def test_lock_serialises_and_is_released() -> None:
    order: list[str] = []

    async def worker(name: str) -> None:
        async with state.renew_confirm_lock(CODE):
            order.append(f"{name}-in")
            await asyncio.sleep(0.01)
            order.append(f"{name}-out")

    async def run() -> None:
        await asyncio.gather(worker("a"), worker("b"))

    asyncio.run(run())
    assert order == ["a-in", "a-out", "b-in", "b-out"]
    assert state.renew_confirm_locks == {}
