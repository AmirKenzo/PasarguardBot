"""Referral reward amount: fixed, or a capped percentage of what the buyer actually paid."""

from __future__ import annotations

from types import SimpleNamespace

from app.services.billing.referral_rewards import (
    ReferralRewardQuote,
    compute_referral_bonus,
    compute_referral_reward,
    describe_referral_bonus,
    describe_referral_reward,
    referral_reward_mode,
)


def _settings(**overrides) -> SimpleNamespace:
    values = {
        "referral_reward_mode": "fixed",
        "referral_reward_amount": 40_000,
        "referral_reward_percent": 10,
        "referral_reward_max": 0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_fixed_reward_ignores_the_purchase_amount() -> None:
    assert compute_referral_reward(_settings(), 1_000_000) == ReferralRewardQuote(amount=40_000)


def test_percent_reward_is_taken_from_the_amount_paid() -> None:
    quote = compute_referral_reward(_settings(referral_reward_mode="percent"), 80_000)
    assert quote == ReferralRewardQuote(amount=8_000, base_amount=80_000, percent=10)


def test_percent_reward_rounds_down_and_respects_the_cap() -> None:
    settings = _settings(referral_reward_mode="percent", referral_reward_percent=15, referral_reward_max=10_000)
    assert compute_referral_reward(settings, 33_333).amount == 4_999
    assert compute_referral_reward(settings, 500_000).amount == 10_000


def test_free_or_bogus_amounts_pay_nothing() -> None:
    settings = _settings(referral_reward_mode="percent")
    assert compute_referral_reward(settings, 0).amount == 0
    assert compute_referral_reward(settings, -5_000).amount == 0


def test_out_of_range_settings_are_clamped() -> None:
    assert (
        compute_referral_reward(_settings(referral_reward_mode="percent", referral_reward_percent=250), 10_000).amount
        == 10_000
    )
    assert referral_reward_mode(_settings(referral_reward_mode="weird")) == "fixed"
    assert compute_referral_reward(_settings(referral_reward_amount=-1), 10_000).amount == 0


def test_description_matches_the_rule() -> None:
    assert describe_referral_reward(_settings()) == "40,000 تومان"
    percent = _settings(referral_reward_mode="percent", referral_reward_max=50_000)
    assert describe_referral_reward(percent) == "10٪ مبلغ اولین خرید (حداکثر 50,000 تومان)"


def test_bonus_side_is_configured_independently() -> None:
    settings = _settings(
        referral_reward_mode="percent",
        referral_bonus_mode="percent",
        referral_bonus_percent=5,
        referral_bonus_max=3_000,
        referral_bonus_amount=20_000,
    )
    assert compute_referral_reward(settings, 100_000).amount == 10_000
    assert compute_referral_bonus(settings, 100_000) == ReferralRewardQuote(
        amount=3_000, base_amount=100_000, percent=5
    )
    fixed_zero = _settings(referral_bonus_mode="fixed", referral_bonus_amount=0)
    assert compute_referral_bonus(fixed_zero, 100_000).amount == 0
    assert describe_referral_bonus(settings) == "5٪ مبلغ اولین خرید (حداکثر 3,000 تومان)"
