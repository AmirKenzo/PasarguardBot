"""A side of a referral that earns nothing is not messaged."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.db.crud import referral as referral_crud
from app.services.billing import referral_rewards


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> dict:
    state: dict = {"messages": [], "call": None, "settings": None}

    async def send_message(peer, text):
        state["messages"].append(peer)

    async def send_log(*args, **kwargs):
        return None

    async def get_settings(self):
        return state["settings"]

    async def process(self, referrer_id, referred_id, **kwargs):
        state["call"] = kwargs
        return True, "ok"

    monkeypatch.setattr(referral_rewards.Kenzo, "send_message", send_message)
    monkeypatch.setattr(referral_rewards, "send_log_message", send_log)
    monkeypatch.setattr(referral_crud.ReferralManager, "get_referral_settings", get_settings)
    monkeypatch.setattr(referral_crud.ReferralManager, "process_referral_reward", process)
    return state


def _settings(**overrides) -> SimpleNamespace:
    values = {
        "referral_enabled": True,
        "referral_reward_mode": "percent",
        "referral_reward_percent": 10,
        "referral_reward_max": 0,
        "referral_reward_amount": 0,
        "referral_bonus_mode": "fixed",
        "referral_bonus_amount": 0,
        "referral_bonus_percent": 5,
        "referral_bonus_max": 0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_zero_bonus_sends_no_message_to_the_invited_user(sent: dict) -> None:
    sent["settings"] = _settings()
    asyncio.run(referral_rewards.process_referral_reward_payout(1, 2, paid_amount=50_000))
    assert sent["messages"] == [1]
    assert sent["call"]["reward_amount"] == 5_000
    assert sent["call"]["bonus_amount"] == 0
    assert sent["call"]["base_amount"] == 50_000


def test_both_sides_are_paid_and_messaged(sent: dict) -> None:
    sent["settings"] = _settings(referral_bonus_mode="percent")
    asyncio.run(referral_rewards.process_referral_reward_payout(1, 2, paid_amount=40_000))
    assert sent["messages"] == [1, 2]
    assert sent["call"]["reward_amount"] == 4_000
    assert sent["call"]["bonus_amount"] == 2_000
    assert sent["call"]["bonus_percent"] == 5
