from sqlalchemy import BigInteger, Boolean, Float, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ResellerBillingSnapshot(Base):
    """One billing row: a usage charge (``used_traffic`` snapshot) or an hourly bucket (``billed_minutes``).

    ``used_traffic`` is the panel's cumulative counter at charge time; ``used_bytes`` is what was
    consumed since the previous charge, ``unit_price`` the rate applied (per GB or per hour) and
    ``period_start`` when the charged period began. Rows written before these columns derive them on read.
    """

    __tablename__ = "reseller_billing_snapshots"
    __table_args__ = (Index("ix_reseller_snapshots_account_time", "account_code", "snapshot_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_code: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    used_traffic: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    billed_amount: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    snapshot_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    billed_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    used_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    unit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    period_start: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    is_debt: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
