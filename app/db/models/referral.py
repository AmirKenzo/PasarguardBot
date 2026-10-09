from sqlalchemy import BigInteger, Boolean, Index, Integer, String, Text
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
    referral_reward_mode: Mapped[str] = mapped_column(String(10), default="fixed", server_default="fixed")
    referral_reward_percent: Mapped[int] = mapped_column(Integer, default=10, server_default="10")
    referral_reward_max: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    referral_bonus_mode: Mapped[str] = mapped_column(String(10), default="fixed", server_default="fixed")
    referral_bonus_percent: Mapped[int] = mapped_column(Integer, default=5, server_default="5")
    referral_bonus_max: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    referral_reward_destination: Mapped[str] = mapped_column(String(10), default="wallet", server_default="wallet")
    referral_withdraw_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    referral_withdraw_min: Mapped[int] = mapped_column(BigInteger, default=50000, server_default="50000")
    referral_transfer_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")

    def __repr__(self):
        return (
            f"<ReferralSettings(id={self.id}, enabled={self.referral_enabled}, reward={self.referral_reward_amount})>"
        )


class ReferralReward(Base):
    __tablename__ = "referral_rewards"
    __table_args__ = (
        Index("ix_refrewards_referrer", "referrer_id"),
        Index("ix_refrewards_referred", "referred_id"),
        Index("uq_refrewards_pair", "referrer_id", "referred_id", unique=True),
        Index("ix_refrewards_payout", "payout_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    referrer_id: Mapped[int] = mapped_column(BigInteger, nullable=False)  # User who referred
    referred_id: Mapped[int] = mapped_column(BigInteger, nullable=False)  # User who was referred
    reward_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)  # Amount given to referrer
    bonus_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)  # Amount given to referred user
    transaction_id: Mapped[int] = mapped_column(BigInteger, nullable=True)  # Related transaction
    base_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reward_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bonus_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payout_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)  # Timestamp
    status: Mapped[str] = mapped_column(
        String(20), default="completed", server_default="'completed'"
    )  # completed (credited to the wallet), available, requested, paid, converted

    def __repr__(self):
        return f"<ReferralReward(id={self.id}, referrer={self.referrer_id}, referred={self.referred_id}, reward={self.reward_amount})>"


class ReferralPayout(Base):
    """A referrer cashing out their referral earnings: by card (reviewed by an admin) or into the wallet."""

    __tablename__ = "referral_payouts"
    __table_args__ = (
        Index("ix_refpayouts_user", "user_id"),
        Index("ix_refpayouts_status", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    card_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    card_holder: Mapped[str | None] = mapped_column(String(100), nullable=True)
    admin_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reviewed_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    def __repr__(self):
        return f"<ReferralPayout(id={self.id}, user={self.user_id}, amount={self.amount}, status={self.status})>"
