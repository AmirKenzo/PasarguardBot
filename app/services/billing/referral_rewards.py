from datetime import datetime

from app import Kenzo
from app.logger import LogType, get_logger
from app.telegram.shared.utils.logging import send_log_message

logger = get_logger(__name__)


async def process_referral_reward_payout(referrer_id: int, referred_id: int) -> None:
    """Handle referral reward creation, payouts, notifications, and logging."""
    try:
        from app.db.crud.referral import ReferralManager

        referral_manager = ReferralManager()
        settings = await referral_manager.get_referral_settings()
        if not settings or not settings.referral_enabled:
            return

        ok, _reason = await referral_manager.process_referral_reward(referrer_id, referred_id)
        if not ok:
            return

        await Kenzo.send_message(
            referrer_id,
            f"🎉 تبریک! شما {settings.referral_reward_amount:,} تومان پاداش دعوت دریافت کردید!\n\n"
            f"👤 کاربر خریدار: {referred_id}\n"
            f"💰 مبلغ پاداش: {settings.referral_reward_amount:,} تومان\n"
            f"🎁 مبلغ هدیه کاربر: {settings.referral_bonus_amount:,} تومان",
        )

        log_message = (
            f"💰 **پرداخت پاداش referral**\n\n"
            f"👤 آیدی referrer: `{referrer_id}`\n"
            f"👤 آیدی کاربر خریدار: `{referred_id}`\n"
            f"💵 مبلغ پاداش referrer: `{settings.referral_reward_amount:,}` تومان\n"
            f"🎁 مبلغ هدیه کاربر: `{settings.referral_bonus_amount:,}` تومان\n"
            f"⏰ زمان: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        await send_log_message(LogType.OTHER, message=log_message)

        await Kenzo.send_message(
            referred_id,
            f"🎁 شما {settings.referral_bonus_amount:,} تومان هدیه دعوت دریافت کردید!\n\n"
            f"👤 دعوت کننده شما: {referrer_id}\n"
            f"💰 مبلغ هدیه: {settings.referral_bonus_amount:,} تومان\n"
            f"🎉 این هدیه به دلیل اولین خرید شما از طریق دعوت تعلق گرفت.",
        )
    except Exception as exc:
        logger.error("Error processing referral rewards: %s", exc)
