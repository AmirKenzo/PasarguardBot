"""Paid upgrades must debit atomically before delivery and refund when delivery fails."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.services.billing import wallet_charge

USER_ID = 7


@pytest.fixture
def wallet(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """In-memory wallet whose debit yields to the loop, like a real DB round-trip."""
    state = SimpleNamespace(balance=0)
    lock = asyncio.Lock()

    async def debit_Money_if_sufficient(user_id: int, amount: int) -> int | None:
        async with lock:  # stands in for SELECT ... FOR UPDATE
            await asyncio.sleep(0)
            if state.balance < amount:
                return None
            state.balance -= amount
            return state.balance

    async def update_Money(user_id: int, Money: int, *, allow_negative: bool = True) -> int:
        state.balance += Money
        return state.balance

    monkeypatch.setattr(wallet_charge, "debit_Money_if_sufficient", debit_Money_if_sufficient)
    monkeypatch.setattr(wallet_charge, "update_Money", update_Money)
    return state


def test_concurrent_upgrades_cannot_overdraw(wallet: SimpleNamespace) -> None:
    wallet.balance = 100
    applied: list[int] = []

    async def deliver() -> int:
        await asyncio.sleep(0)  # panel call
        applied.append(1)
        return len(applied)

    async def run() -> list:
        return await asyncio.gather(*(wallet_charge.charge_then_apply(USER_ID, 100, deliver) for _ in range(5)))

    results = asyncio.run(run())

    assert sum(r is not None for r in results) == 1
    assert len(applied) == 1
    assert wallet.balance == 0


def test_insufficient_balance_applies_nothing(wallet: SimpleNamespace) -> None:
    wallet.balance = 50
    applied: list[int] = []

    async def deliver() -> None:
        applied.append(1)

    assert asyncio.run(wallet_charge.charge_then_apply(USER_ID, 100, deliver)) is None
    assert applied == []
    assert wallet.balance == 50


def test_failed_delivery_is_refunded(wallet: SimpleNamespace) -> None:
    wallet.balance = 100

    async def deliver() -> None:
        raise RuntimeError("panel down")

    with pytest.raises(RuntimeError):
        asyncio.run(wallet_charge.charge_then_apply(USER_ID, 100, deliver))
    assert wallet.balance == 100


def test_success_returns_result_and_new_balance(wallet: SimpleNamespace) -> None:
    wallet.balance = 150

    async def deliver() -> str:
        return "done"

    assert asyncio.run(wallet_charge.charge_then_apply(USER_ID, 100, deliver)) == ("done", 50)
