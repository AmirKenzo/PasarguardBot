from sqlalchemy import BigInteger, Boolean, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ZarinpalPayment(Base):
    """A Zarinpal balance top-up (live or sandbox). `amount` is in toman; Zarinpal is sent rials."""

    __tablename__ = "zarinpal_payments"
    __table_args__ = (
        Index("ix_zarinpal_order_id", "order_id", unique=True),
        Index("ix_zarinpal_authority", "authority"),
        Index("ix_zarinpal_user_status", "user_id", "status"),
        Index("ix_zarinpal_status", "status"),
    )

    # Random id in a range above TonPays and crypto ids, so direct-pay can link it the same way.
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    order_id: Mapped[str] = mapped_column(String(20), nullable=False)
    authority: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sandbox: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source: Mapped[str] = mapped_column(String(10), nullable=False, default="bot")
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    credited_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    ref_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    card_pan: Mapped[str | None] = mapped_column(String(32), nullable=True)
    message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    paid_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
