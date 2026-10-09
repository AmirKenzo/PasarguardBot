from sqlalchemy import BigInteger, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ResellerBillingSnapshot(Base):
    """One billing row: a usage charge (``used_traffic`` snapshot) or an hourly bucket (``billed_minutes``)."""

    __tablename__ = "reseller_billing_snapshots"
    __table_args__ = (Index("ix_reseller_snapshots_account_time", "account_code", "snapshot_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_code: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    used_traffic: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    billed_amount: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    snapshot_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    billed_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
