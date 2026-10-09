"""The invoice shows a shortfall only when the wallet cannot cover it."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.services.billing import direct_pay_flow


@pytest.fixture
def wallet(monkeypatch: pytest.MonkeyPatch) -> dict:
    state = {"balance": 0, "direct": True}

    async def read_user(self, user_id: int):
        return SimpleNamespace(amount=state["balance"], language="fa")

    async def direct_enabled() -> bool:
        return state["direct"]

    async def bot_text(*, key: str, default: str, lang: str) -> str:
        return f"{key}|{default}"

    monkeypatch.setattr(direct_pay_flow.UserCRUD, "read_user", read_user)
    monkeypatch.setattr(direct_pay_flow, "is_direct_pay_enabled", direct_enabled)
    monkeypatch.setattr(direct_pay_flow, "is_direct_pay_renew_enabled", direct_enabled)
    monkeypatch.setattr(direct_pay_flow, "get_bot_text", bot_text)
    return state


def test_covered_invoice_has_no_notice(wallet: dict) -> None:
    wallet["balance"] = 50_000
    assert asyncio.run(direct_pay_flow.invoice_shortfall_notice(1, 50_000)) is None
    assert asyncio.run(direct_pay_flow.invoice_shortfall_notice(1, 10_000)) is None


def test_short_invoice_shows_balance_and_shortfall(wallet: dict) -> None:
    wallet["balance"] = 15_000
    notice = asyncio.run(direct_pay_flow.invoice_shortfall_notice(1, 40_000))
    assert notice is not None
    assert notice.startswith("invoice_shortfall_direct_pay|")
    assert "15,000" in notice
    assert "25,000" in notice


def test_short_invoice_without_direct_pay_uses_plain_notice(wallet: dict) -> None:
    wallet["balance"] = 0
    wallet["direct"] = False
    notice = asyncio.run(direct_pay_flow.invoice_shortfall_notice(1, 40_000, renew=True))
    assert notice is not None
    assert notice.startswith("invoice_shortfall|")
    assert "40,000" in notice
