"""Referral payout on an invited user's first purchase: amounts, payout and notices.

Both sides are configured the same way and independently:

* the referrer's **reward** — ``referral_reward_mode`` / ``_amount`` / ``_percent`` / ``_max``
* the invited user's **bonus** — ``referral_bonus_mode`` / ``_amount`` / ``_percent`` / ``_max``

``fixed`` pays the amount; ``percent`` pays that share of what the invited user
actually paid (after any discount code), capped by ``_max`` when it is above
zero. Either side can be zero, and a side that earns nothing gets no message.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app import Kenzo
from app.logger import LogType, get_logger
from app.telegram.shared.utils.logging import send_log_message

logger = get_logger(__name__)

REWARD_MODE_FIXED = "fixed"
REWARD_MODE_PERCENT = "percent"
REWARD_MODES: tuple[str, ...] = (REWARD_MODE_FIXED, REWARD_MODE_PERCENT)
REWARD_PERCENT_MIN = 1
REWARD_PERCENT_MAX = 100

SIDE_REWARD = "reward"  # the referrer
SIDE_BONUS = "bonus"  # the invited user


@dataclass(frozen=True)
class ReferralRewardQuote:
    amount: int
    # Only set for percentage payouts: what the percentage was taken of, and how much.
    base_amount: int | None = None
    percent: int | None = None


def _setting(settings, side: str, field: str, default: int | str):
    return getattr(settings, f"referral_{side}_{field}", default)


def referral_side_mode(settings, side: str) -> str:
    mode = str(_setting(settings, side, "mode", REWARD_MODE_FIXED) or REWARD_MODE_FIXED)
    return mode if mode in REWARD_MODES else REWARD_MODE_FIXED


def referral_reward_mode(settings) -> str:
    return referral_side_mode(settings, SIDE_REWARD)


def compute_referral_side(settings, side: str, paid_amount: int) -> ReferralRewardQuote:
    """What ``side`` earns for a first purchase of ``paid_amount``.

    ``paid_amount`` must be what was actually taken from the buyer's wallet — the
    final price after any discount code — never a price shown on an invoice.
    """
    if referral_side_mode(settings, side) != REWARD_MODE_PERCENT:
        return ReferralRewardQuote(amount=max(int(_setting(settings, side, "amount", 0) or 0), 0))

    percent = min(max(int(_setting(settings, side, "percent", 0) or 0), 0), REWARD_PERCENT_MAX)
    base = max(int(paid_amount or 0), 0)
    amount = base * percent // 100
    cap = int(_setting(settings, side, "max", 0) or 0)
    if cap > 0:
        amount = min(amount, cap)
    return ReferralRewardQuote(amount=amount, base_amount=base, percent=percent)


def compute_referral_reward(settings, paid_amount: int) -> ReferralRewardQuote:
    return compute_referral_side(settings, SIDE_REWARD, paid_amount)


def compute_referral_bonus(settings, paid_amount: int) -> ReferralRewardQuote:
    return compute_referral_side(settings, SIDE_BONUS, paid_amount)


def describe_referral_side(settings, side: str) -> str:
    """Human wording of one side's rule, for banners, stats and admin screens."""
    if referral_side_mode(settings, side) != REWARD_MODE_PERCENT:
        return f"{int(_setting(settings, side, 'amount', 0) or 0):,} تومان"
    percent = int(_setting(settings, side, "percent", 0) or 0)
    text = f"{percent}٪ مبلغ اولین خرید"
    cap = int(_setting(settings, side, "max", 0) or 0)
    if cap > 0:
        text += f" (حداکثر {cap:,} تومان)"
    return text


def describe_referral_reward(settings) -> str:
    return describe_referral_side(settings, SIDE_REWARD)


def describe_referral_bonus(settings) -> str:
    return describe_referral_side(settings, SIDE_BONUS)


def _how(quote: ReferralRewardQuote) -> str:
    if quote.percent is None:
        return ""
    return f" ({quote.percent}٪ از خرید {quote.base_amount:,} تومان)"


async def process_referral_reward_payout(referrer_id: int, referred_id: int, *, paid_amount: int) -> None:
    """Pay a referral pair once, on the invited user's first purchase, and notify whoever earned something."""
    try:
        from app.db.crud.referral import ReferralManager

        referral_manager = ReferralManager()
        settings = await referral_manager.get_referral_settings()
        if not settings or not settings.referral_enabled:
            return

        reward = compute_referral_reward(settings, paid_amount)
        bonus = compute_referral_bonus(settings, paid_amount)
        ok, _reason = await referral_manager.process_referral_reward(
            referrer_id,
            referred_id,
            reward_amount=reward.amount,
            bonus_amount=bonus.amount,
            base_amount=reward.base_amount if reward.base_amount is not None else bonus.base_amount,
            reward_percent=reward.percent,
            bonus_percent=bonus.percent,
        )
        if not ok:
            return

        if reward.amount > 0:
            bonus_line = f"🎁 هدیهٔ کاربر دعوت‌شده: {bonus.amount:,} تومان\n" if bonus.amount > 0 else ""
            await Kenzo.send_message(
                referrer_id,
                f"🎉 تبریک! شما {reward.amount:,} تومان پاداش دعوت دریافت کردید!\n\n"
                f"👤 کاربر خریدار: {referred_id}\n"
                f"💰 مبلغ پاداش: {reward.amount:,} تومان{_how(reward)}\n"
                f"{bonus_line}",
            )

        log_message = (
            f"💰 **پرداخت پاداش referral**\n\n"
            f"👤 آیدی referrer: `{referrer_id}`\n"
            f"👤 آیدی کاربر خریدار: `{referred_id}`\n"
            f"💵 پاداش referrer: `{reward.amount:,}` تومان{_how(reward)}\n"
            f"🎁 هدیهٔ کاربر: `{bonus.amount:,}` تومان{_how(bonus)}\n"
            f"⏰ زمان: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        await send_log_message(LogType.OTHER, message=log_message)

        if bonus.amount > 0:
            await Kenzo.send_message(
                referred_id,
                f"🎁 شما {bonus.amount:,} تومان هدیه دعوت دریافت کردید!\n\n"
                f"👤 دعوت کننده شما: {referrer_id}\n"
                f"💰 مبلغ هدیه: {bonus.amount:,} تومان{_how(bonus)}\n"
                f"🎉 این هدیه به دلیل اولین خرید شما از طریق دعوت تعلق گرفت.",
            )
    except Exception as exc:
        logger.error("Error processing referral rewards: %s", exc)
