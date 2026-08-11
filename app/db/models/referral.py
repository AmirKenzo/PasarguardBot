from sqlalchemy import BigInteger, Boolean, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReferralSettings(Base):
    __tablename__ = "referral_settings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # Referral system settings
    referral_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    referral_reward_amount: Mapped[int] = mapped_column(
        BigInteger, default=40000, server_default="40000"
    )  # Reward for referrer
    referral_bonus_amount: Mapped[int] = mapped_column(
        BigInteger, default=40000, server_default="40000"
    )  # Bonus for referred user
    referral_banner_text: Mapped[str] = mapped_column(Text, nullable=True)

    def __repr__(self):
        return (
            f"<ReferralSettings(id={self.id}, enabled={self.referral_enabled}, reward={self.referral_reward_amount})>"
        )


class ReferralReward(Base):
    __tablename__ = "referral_rewards"
    __table_args__ = (
        Index("ix_refrewards_referrer", "referrer_id"),
        Index("ix_refrewards_referred", "referred_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    referrer_id: Mapped[int] = mapped_column(BigInteger, nullable=False)  # User who referred
    referred_id: Mapped[int] = mapped_column(BigInteger, nullable=False)  # User who was referred
    reward_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)  # Amount given to referrer
    bonus_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)  # Amount given to referred user
    transaction_id: Mapped[int] = mapped_column(BigInteger, nullable=True)  # Related transaction
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)  # Timestamp
    status: Mapped[str] = mapped_column(
        String(20), default="completed", server_default="'completed'"
    )  # completed, pending, failed

    def __repr__(self):
        return f"<ReferralReward(id={self.id}, referrer={self.referrer_id}, referred={self.referred_id}, reward={self.reward_amount})>"
