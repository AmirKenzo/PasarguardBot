"""Bot resellers: people who sell panel users through the web app without any panel access.

The bot's own panel credential owns every user they create; these tables record which user
belongs to which reseller and bill each one per GB of traffic from the reseller's wallet.
"""

from sqlalchemy import BigInteger, Boolean, Float, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

GRANT_PENDING = "pending"
GRANT_APPROVED = "approved"
GRANT_REJECTED = "rejected"
GRANT_REVOKED = "revoked"

RESELLER_ACTIVE = "active"
RESELLER_FROZEN = "frozen"
RESELLER_SUSPENDED = "suspended"

DISABLED_BY_SYSTEM = "system"
DISABLED_BY_RESELLER = "reseller"
DISABLED_BY_ADMIN = "admin"

NAMING_TELEGRAM_ID = "{id}"


class BotResellerService(Base):
    """A sellable bundle the admin defines: a set of panel groups and a price per GB."""

    __tablename__ = "bot_reseller_services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    panel_code: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    group_ids: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    price_per_gb: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sale_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    max_users: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_user_gb: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    max_user_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)


class BotReseller(Base):
    """One row per person; their grants say which services they may sell."""

    __tablename__ = "bot_resellers"
    __table_args__ = (UniqueConstraint("telegram_id", name="uq_bot_reseller_tgid"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=RESELLER_ACTIVE)
    username_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    username_suffix: Mapped[str] = mapped_column(String(16), nullable=False, default="", server_default="")
    carry: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    warned_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    frozen_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)


class BotResellerGrant(Base):
    """A reseller's right to sell one service, from request to approval (or rejection)."""

    __tablename__ = "bot_reseller_grants"
    __table_args__ = (
        UniqueConstraint("reseller_id", "service_id", name="uq_bot_reseller_grant"),
        Index("ix_bot_reseller_grant_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reseller_id: Mapped[int] = mapped_column(Integer, nullable=False)
    service_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=GRANT_PENDING)
    price_per_gb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_users: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_user_gb: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_user_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reject_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    decided_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    decided_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class BotResellerUser(Base):
    """A panel user a reseller created; ``baseline_bytes`` is the traffic already paid for."""

    __tablename__ = "bot_reseller_users"
    __table_args__ = (
        UniqueConstraint("panel_code", "panel_user_id", name="uq_bot_reseller_panel_user"),
        Index("ix_bot_reseller_user_owner", "reseller_id", "deleted_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reseller_id: Mapped[int] = mapped_column(Integer, nullable=False)
    service_id: Mapped[int] = mapped_column(Integer, nullable=False)
    panel_code: Mapped[int] = mapped_column(Integer, nullable=False)
    panel_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(48), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    baseline_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    disabled_by: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    deleted_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class BotResellerUsageHourly(Base):
    """Traffic and money of one service in one clock hour; the per-minute job adds to it."""

    __tablename__ = "bot_reseller_usage_hourly"
    __table_args__ = (UniqueConstraint("reseller_id", "service_id", "hour", name="uq_bot_reseller_usage_hour"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reseller_id: Mapped[int] = mapped_column(Integer, nullable=False)
    service_id: Mapped[int] = mapped_column(Integer, nullable=False)
    hour: Mapped[int] = mapped_column(BigInteger, nullable=False)
    bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
