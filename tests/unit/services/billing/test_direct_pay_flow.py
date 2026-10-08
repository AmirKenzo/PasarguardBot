"""Direct-pay top-up must deliver the product the amount was quoted for, not whatever is in the session later."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from app.services.billing import direct_pay_flow, direct_pay_store

USER_ID = 42


@pytest.fixture
def session(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """In-memory replacement for the per-user Redis state used by the flow."""
    store: dict[str, Any] = {}
    saved: list[dict[str, Any]] = []

    async def get_data(user_id: int, key: str) -> Any:
        return store.get(key)

    async def set_data(user_id: int, key: str, value: Any, ttl: int | None = None) -> None:
        store[key] = value

    async def clear_user(user_id: int) -> None:
        store.clear()

    async def noop(*args: Any, **kwargs: Any) -> None:
        return None

    async def enabled() -> bool:
        return True

    async def save_pending(**kwargs: Any) -> None:
        saved.append(kwargs)

    async def read_user(self, user_id: int) -> SimpleNamespace:
        return SimpleNamespace(amount=0, language="fa")

    async def get_bot_text(key: str, default: str, lang: str) -> str:
        return default

    async def get_settings(self) -> None:
        return None

    monkeypatch.setattr(direct_pay_flow, "get_data", get_data)
    monkeypatch.setattr(direct_pay_flow, "set_data", set_data)
    monkeypatch.setattr(direct_pay_flow, "clear_user", clear_user)
    monkeypatch.setattr(direct_pay_flow, "set_step", noop)
    monkeypatch.setattr(direct_pay_flow, "is_direct_pay_enabled", enabled)
    monkeypatch.setattr(direct_pay_flow, "is_direct_pay_renew_enabled", enabled)
    monkeypatch.setattr(direct_pay_flow, "get_bot_text", get_bot_text)
    monkeypatch.setattr(direct_pay_flow, "create_inline_cartbcard", noop)
    monkeypatch.setattr(direct_pay_flow.UserCRUD, "read_user", read_user)
    monkeypatch.setattr(direct_pay_flow.SettingsManager, "get_settings", get_settings)
    monkeypatch.setattr(direct_pay_store, "save_pending", save_pending)
    return SimpleNamespace(store=store, saved=saved)


def _event() -> SimpleNamespace:
    async def edit(*args: Any, **kwargs: Any) -> None:
        return None

    return SimpleNamespace(sender_id=USER_ID, message_id=1, edit=edit)


def test_topup_uses_plan_snapshot_taken_with_amount(session: SimpleNamespace) -> None:
    saved = session.saved
    session.store.update({"panel": 1, "selected_plan_id": 10, "gig": 1, "username": "cheap"})
    asyncio.run(direct_pay_flow.mark_direct_pay_ready(USER_ID, kind=direct_pay_store.KIND_VPN, amount=10))

    # User goes back to the shop and picks an expensive plan without confirming it.
    session.store.update({"selected_plan_id": 20, "gig": 100, "username": "expensive"})

    assert asyncio.run(direct_pay_flow.start_direct_pay_topup(_event())) is True
    assert len(saved) == 1
    assert saved[0]["amount"] == 10
    assert saved[0]["payload"]["selected_plan_id"] == 10
    assert saved[0]["payload"]["gig"] == 1
    assert saved[0]["payload"]["username"] == "cheap"


def test_reconfirming_new_plan_replaces_amount_and_snapshot_together(session: SimpleNamespace) -> None:
    saved = session.saved
    session.store.update({"panel": 1, "selected_plan_id": 10, "gig": 1, "username": "u"})
    asyncio.run(direct_pay_flow.mark_direct_pay_ready(USER_ID, kind=direct_pay_store.KIND_VPN, amount=10))

    session.store.update({"selected_plan_id": 20, "gig": 100})
    asyncio.run(direct_pay_flow.mark_direct_pay_ready(USER_ID, kind=direct_pay_store.KIND_VPN, amount=120))

    assert asyncio.run(direct_pay_flow.start_direct_pay_topup(_event())) is True
    assert saved[0]["amount"] == 120
    assert saved[0]["payload"]["selected_plan_id"] == 20


def test_renew_snapshot_keeps_original_service(session: SimpleNamespace) -> None:
    saved = session.saved
    session.store.update({"ConfigID": 555, "panel": 1, "selected_plan_id": 10})
    asyncio.run(direct_pay_flow.mark_direct_pay_ready(USER_ID, kind=direct_pay_store.KIND_RENEW, amount=10))

    session.store.update({"ConfigID": 777, "selected_plan_id": 20})

    assert asyncio.run(direct_pay_flow.start_direct_pay_topup(_event())) is True
    assert saved[0]["amount"] == 10
    assert saved[0]["payload"]["service_code"] == 555
    assert saved[0]["payload"]["selected_plan_id"] == 10


def test_topup_without_snapshot_is_refused(session: SimpleNamespace) -> None:
    # State written by an older bot version (amount without a frozen payload).
    session.store.update(
        {
            direct_pay_flow.REDIS_DIRECT_PAY_READY: "1",
            direct_pay_flow.REDIS_DIRECT_PAY_KIND: direct_pay_store.KIND_VPN,
            direct_pay_flow.REDIS_DIRECT_PAY_AMOUNT: 10,
            "selected_plan_id": 20,
        }
    )

    assert asyncio.run(direct_pay_flow.start_direct_pay_topup(_event())) is False
    assert session.saved == []
