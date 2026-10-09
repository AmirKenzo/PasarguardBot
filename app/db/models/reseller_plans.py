from sqlalchemy import BigInteger, Boolean, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

PRICING_MODES = ("fixed", "unlimited", "per_gb", "per_tb", "hourly", "usage")
# New plans can only use these; the other modes stay billable for plans created before.
CREATABLE_PRICING_MODES = ("fixed", "unlimited", "usage", "hourly")


class ResellerPlan(Base):
    __tablename__ = "reseller_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    panel_code: Mapped[int] = mapped_column(Integer, nullable=False)
    pricing_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="fixed")
    price: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    min_volume: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    max_volume: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    volume_step: Mapped[float] = mapped_column(Float, nullable=False, default=1)
    data_limit: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    max_users: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    role_id: Mapped[int] = mapped_column(Integer, nullable=False)
    role_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    allowed_group_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    permission_overrides: Mapped[str | None] = mapped_column(Text, nullable=True)
    enable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    display_button_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    button_style: Mapped[str | None] = mapped_column(String(20), nullable=True)
    button_icon: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    addon_day_price: Mapped[float] = mapped_column(Float, nullable=False, default=0, server_default="0")
    addon_gb_price: Mapped[float] = mapped_column(Float, nullable=False, default=0, server_default="0")
    addon_user_price: Mapped[float] = mapped_column(Float, nullable=False, default=0, server_default="0")
