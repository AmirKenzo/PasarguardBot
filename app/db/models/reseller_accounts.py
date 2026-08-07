from sqlalchemy import BigInteger, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ResellerAccount(Base):
    __tablename__ = "reseller_accounts"
    __table_args__ = (
        Index("ix_reseller_tgid", "telegram_id"),
        Index("ix_reseller_status_expiry", "status", "expiration_time"),
        Index("ix_reseller_panel_username", "panel_code", "username"),
    )

    code: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    panel_code: Mapped[int] = mapped_column(Integer, nullable=False)
    panel_admin_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    password_encrypted: Mapped[str] = mapped_column(String(512), nullable=False)
    plan_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pricing_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="fixed")
    data_limit: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    max_users: Mapped[int | None] = mapped_column(Integer, nullable=True)
    purchased_volume: Mapped[float | None] = mapped_column(Float, nullable=True)
    usage_cap_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    createtime: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    expiration_time: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    billing_state: Mapped[str | None] = mapped_column(Text, nullable=True)
