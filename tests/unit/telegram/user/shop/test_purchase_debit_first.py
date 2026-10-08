"""Bot VPN purchase charges the wallet before creating the panel user, and refunds on panel failure."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from app.telegram.user.shop import helpers

USER_ID = 9
PRICE = 100


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    state = SimpleNamespace(balance=0, panel_calls=0, refunds=[], panel_error=None)
    plan = SimpleNamespace(plan_type="normal", data_limit_reset_strategy=None, duration=30, ip_limit=0, price=PRICE)

    async def lang(user_id: int) -> str:
        return "fa"

    async def load_context(user_id: int):
        return 10, 1, plan

    async def get_data(user_id: int, key: str) -> str:
        return "cfg_user"

    async def get_panel(self, code: int):
        return SimpleNamespace(base_url="https://panel.invalid", cookie="c")

    async def groups(panel):
        return []

    async def debit(user_id: int, amount: int):
        if state.balance < amount:
            return None
        state.balance -= amount
        return state.balance

    async def update_money(user_id: int, Money: int, **kwargs: Any):
        state.refunds.append(Money)
        state.balance += Money
        return state.balance

    class FakeAPI:
        def __init__(self, base_url: str) -> None:
            pass

        async def add_user(self, user, token):
            state.panel_calls += 1
            if state.panel_error:
                raise state.panel_error
            raise AssertionError("stop after panel call")  # success path is out of scope here

    async def send_message(*args: Any, **kwargs: Any) -> None:
        return None

    async def home_buttons(*args: Any) -> list:
        return []

    monkeypatch.setattr(helpers, "_user_lang", lang)
    monkeypatch.setattr(helpers, "_load_purchase_context", load_context)
    monkeypatch.setattr(helpers, "get_data", get_data)
    monkeypatch.setattr(helpers.PanelsManager, "get_panel_by_code", get_panel)
    monkeypatch.setattr(helpers, "fetch_panel_groups_with_auth", groups)
    monkeypatch.setattr(helpers, "resolve_panel_group_ids", lambda panel, resp: [])
    monkeypatch.setattr(helpers, "debit_Money_if_sufficient", debit)
    monkeypatch.setattr(helpers, "update_Money", update_money)
    monkeypatch.setattr(helpers, "PasarguardAPI", FakeAPI)
    monkeypatch.setattr(helpers.Kenzo, "send_message", send_message)
    monkeypatch.setattr(helpers, "bhome_buttons", home_buttons)
    return state


def _buy():
    return asyncio.run(helpers.create_vpn_purchase_for_user(USER_ID, amount=PRICE))


def test_insufficient_balance_creates_nothing(env: SimpleNamespace) -> None:
    env.balance = PRICE - 1
    assert _buy() == (False, "insufficient_balance")
    assert env.panel_calls == 0
    assert env.balance == PRICE - 1


def test_panel_failure_refunds_the_charge(env: SimpleNamespace) -> None:
    env.balance = PRICE
    env.panel_error = RuntimeError("panel down")
    with pytest.raises(RuntimeError):
        _buy()
    assert env.panel_calls == 1
    assert env.refunds == [PRICE]
    assert env.balance == PRICE
