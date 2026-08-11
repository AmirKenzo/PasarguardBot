import time

from sqlalchemy import case, func, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.future import select

from app.db.base import AsyncSessionLocal as Session
from app.db.models.referral import ReferralReward, ReferralSettings
from app.db.models.user import User
from app.logger import get_logger

log = get_logger(__name__)


class ReferralSettingsCRUD:
    async def get_settings(self):
        """Get referral settings"""
        async with Session() as session:
            try:
                result = await session.execute(select(ReferralSettings))
                settings = result.scalars().first()
                if not settings:
                    # Create default settings if none exist
                    settings = await self.create_default_settings()
                return settings
            except SQLAlchemyError as e:
                log.error("Error retrieving referral settings: %s", e)
                return None

    async def create_default_settings(self):
        """Create default referral settings"""
        async with Session() as session:
            try:
                default_settings = ReferralSettings(
                    referral_enabled=True,
                    referral_reward_amount=40000,
                    referral_bonus_amount=40000,
                    referral_banner_text="• انتقال حجم باقیمانده به دوره بعدی\n• شروع قیمت از 10 هزار تومان\n• فعال روی تمامی اپراتورها\n• قابل استفاده در 2 دستگاه\n• امکان تغییر سرور و لوکیشن\n• امکان تغییر لینک و پروتکل\n• تنوع کشور و موقعیت سرور\n• آیفون / اندروید / ویندوز / مک\n• پشتیبانی از ChatGPT و Spotify\n\n🔥 {referral_link}\n\n✅ ربات رو با لینک بالا استارت کن و پس از ثبت نام اعتبار رایگان هدیه بگیر !\n\n👆🏻 بنر و لینک ریفرال اختصاصی شما برای دعوت دیگران\n\n❕پس از عضویت و خرید، مبلغ هدیه به صورت خودکار برای هردو طرف در کیف پول افزوده میشود.",
                )
                session.add(default_settings)
                await session.commit()
                return default_settings
            except SQLAlchemyError as e:
                await session.rollback()
                log.error("Error creating default referral settings: %s", e)
                return None

    async def update_settings(self, **kwargs):
        """Update referral settings"""
        async with Session() as session:
            try:
                result = await session.execute(select(ReferralSettings))
                settings = result.scalars().first()
                if settings:
                    for key, value in kwargs.items():
                        if hasattr(settings, key):
                            setattr(settings, key, value)
                    await session.commit()
                    return settings
                return None
            except SQLAlchemyError as e:
                await session.rollback()
                log.error("Error updating referral settings: %s", e)
                return None

    async def toggle_referral_system(self):
        """Toggle referral system on/off"""
        async with Session() as session:
            try:
                result = await session.execute(select(ReferralSettings))
                settings = result.scalars().first()
                if settings:
                    settings.referral_enabled = not settings.referral_enabled
                    await session.commit()
                    return settings.referral_enabled
                return None
            except SQLAlchemyError as e:
                await session.rollback()
                log.error("Error toggling referral system: %s", e)
                return None


class ReferralRewardCRUD:
    async def create_reward(self, referrer_id, referred_id, reward_amount, bonus_amount, transaction_id=None):
        """Create a new referral reward record"""
        async with Session() as session:
            try:
                reward = ReferralReward(
                    referrer_id=referrer_id,
                    referred_id=referred_id,
                    reward_amount=reward_amount,
                    bonus_amount=bonus_amount,
                    transaction_id=transaction_id,
                    created_at=int(time.time()),
                    status="completed",
                )
                session.add(reward)
                await session.commit()
                return reward
            except SQLAlchemyError as e:
                await session.rollback()
                log.error("Error creating referral reward: %s", e)
                return None

    async def get_referrer_rewards(self, referrer_id):
        """Get all rewards for a referrer"""
        async with Session() as session:
            try:
                result = await session.execute(select(ReferralReward).filter_by(referrer_id=referrer_id))
                return result.scalars().all()
            except SQLAlchemyError as e:
                log.error("Error getting referrer rewards: %s", e)
                return []

    async def get_referred_rewards(self, referred_id):
        """Get all rewards for a referred user"""
        async with Session() as session:
            try:
                result = await session.execute(select(ReferralReward).filter_by(referred_id=referred_id))
                return result.scalars().all()
            except SQLAlchemyError as e:
                log.error("Error getting referred rewards: %s", e)
                return []

    async def get_user_stats(self, user_id) -> dict:
        """Count and total earnings for a referrer in one query."""
        async with Session() as session:
            try:
                stmt = select(
                    func.count(ReferralReward.id).label("count"),
                    func.sum(ReferralReward.reward_amount).label("total_earnings"),
                ).filter_by(referrer_id=user_id)
                row = (await session.execute(stmt)).one()
                return {
                    "referral_count": int(row.count or 0),
                    "total_earnings": int(row.total_earnings or 0),
                }
            except SQLAlchemyError as e:
                log.error("Error getting referral user stats: %s", e)
                return {"referral_count": 0, "total_earnings": 0}

    async def get_total_referral_earnings(self, user_id):
        """Get total earnings from referrals for a user"""
        return (await self.get_user_stats(user_id))["total_earnings"]

    async def get_referral_count(self, user_id):
        """Get number of successful referrals for a user"""
        return (await self.get_user_stats(user_id))["referral_count"]

    async def get_period_stats(self, start_ts: int, end_ts: int | None = None) -> dict:
        """Referral rewards paid in [start_ts, end_ts) — count and reward_amount sum."""
        async with Session() as session:
            try:
                cond = (ReferralReward.status == "completed") & (ReferralReward.created_at >= start_ts)
                if end_ts is not None:
                    cond = cond & (ReferralReward.created_at < end_ts)
                stmt = select(
                    func.count().label("count"),
                    func.sum(ReferralReward.reward_amount).label("reward_sum"),
                    func.sum(ReferralReward.bonus_amount).label("bonus_sum"),
                ).where(cond)
                row = (await session.execute(stmt)).one()
                return {
                    "count": int(row.count or 0),
                    "reward_sum": int(row.reward_sum or 0),
                    "bonus_sum": int(row.bonus_sum or 0),
                }
            except SQLAlchemyError as e:
                log.error("Error getting referral period stats: %s", e)
                return {"count": 0, "reward_sum": 0, "bonus_sum": 0}

    async def get_dashboard_stats(self, ts: dict) -> dict:
        """Today / yesterday / all-time referral reward totals."""
        async with Session() as session:
            try:
                today = ts["today_ts"]
                yesterday = ts["yesterday_ts"]
                completed = ReferralReward.status == "completed"
                stmt = select(
                    func.sum(
                        case(
                            ((completed) & (ReferralReward.created_at >= today), ReferralReward.reward_amount),
                            else_=0,
                        )
                    ).label("today"),
                    func.sum(
                        case(
                            (
                                (completed)
                                & (ReferralReward.created_at >= yesterday)
                                & (ReferralReward.created_at < today),
                                ReferralReward.reward_amount,
                            ),
                            else_=0,
                        )
                    ).label("yesterday"),
                    func.sum(case((completed, ReferralReward.reward_amount), else_=0)).label("all_time"),
                    func.sum(case(((completed) & (ReferralReward.created_at >= today), 1), else_=0)).label(
                        "count_today"
                    ),
                    func.sum(
                        case(
                            (
                                (completed)
                                & (ReferralReward.created_at >= yesterday)
                                & (ReferralReward.created_at < today),
                                1,
                            ),
                            else_=0,
                        )
                    ).label("count_yesterday"),
                    func.sum(case((completed, 1), else_=0)).label("count_all"),
                ).select_from(ReferralReward)
                row = (await session.execute(stmt)).one()
                return {
                    "today": int(row.today or 0),
                    "yesterday": int(row.yesterday or 0),
                    "all_time": int(row.all_time or 0),
                    "count_today": int(row.count_today or 0),
                    "count_yesterday": int(row.count_yesterday or 0),
                    "count_all": int(row.count_all or 0),
                }
            except SQLAlchemyError as e:
                log.error("Error getting referral dashboard stats: %s", e)
                return {
                    "today": 0,
                    "yesterday": 0,
                    "all_time": 0,
                    "count_today": 0,
                    "count_yesterday": 0,
                    "count_all": 0,
                }

    async def check_referral_exists(self, referrer_id, referred_id):
        """Check if a referral relationship already exists"""
        async with Session() as session:
            try:
                result = await session.execute(
                    select(ReferralReward).filter_by(referrer_id=referrer_id, referred_id=referred_id)
                )
                return result.scalars().first() is not None
            except SQLAlchemyError as e:
                log.error("Error checking referral existence: %s", e)
                return False


class ReferralManager:
    def __init__(self):
        self.settings_crud = ReferralSettingsCRUD()
        self.reward_crud = ReferralRewardCRUD()

    async def is_referral_enabled(self):
        """Check if referral system is enabled"""
        settings = await self.settings_crud.get_settings()
        return settings.referral_enabled if settings else False

    async def get_referral_settings(self):
        """Get current referral settings"""
        return await self.settings_crud.get_settings()

    async def process_referral_reward(self, referrer_id, referred_id, transaction_id=None):
        """Process referral reward when a referred user makes a purchase.

        Check + insert + balance credit run in one session/transaction.
        """
        settings = await self.get_referral_settings()
        if not settings or not settings.referral_enabled:
            return False, "Referral system is disabled"

        reward_amount = int(settings.referral_reward_amount or 0)
        bonus_amount = int(settings.referral_bonus_amount or 0)
        try:
            async with Session() as session:
                exists = await session.execute(
                    select(ReferralReward.id)
                    .where(
                        ReferralReward.referrer_id == referrer_id,
                        ReferralReward.referred_id == referred_id,
                    )
                    .limit(1)
                )
                if exists.scalar_one_or_none() is not None:
                    return False, "Referral already processed"

                session.add(
                    ReferralReward(
                        referrer_id=referrer_id,
                        referred_id=referred_id,
                        reward_amount=reward_amount,
                        bonus_amount=bonus_amount,
                        transaction_id=transaction_id,
                        created_at=int(time.time()),
                        status="completed",
                    )
                )
                if reward_amount:
                    await session.execute(
                        update(User)
                        .where(User.id == referrer_id)
                        .values(amount=func.coalesce(User.amount, 0) + reward_amount)
                    )
                if bonus_amount:
                    await session.execute(
                        update(User)
                        .where(User.id == referred_id)
                        .values(amount=func.coalesce(User.amount, 0) + bonus_amount)
                    )
                await session.commit()
                return True, "Referral reward processed successfully"
        except SQLAlchemyError as e:
            log.error("Error processing referral reward: %s", e)
            return False, "Failed to process referral reward"

    async def get_user_referral_stats(self, user_id):
        """Get referral statistics for a user"""
        return await self.reward_crud.get_user_stats(user_id)
