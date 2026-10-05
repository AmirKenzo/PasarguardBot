from sqlalchemy import BigInteger, Boolean, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TonPaysInvoice(Base):
    """A TonPays balance top-up invoice (standard or custom Telegram gateway)."""

    __tablename__ = "tonpays_invoices"
    __table_args__ = (
        Index("ix_tonpays_order_id", "order_id", unique=True),
        Index("ix_tonpays_invoice_id", "invoice_id"),
        Index("ix_tonpays_user_status", "user_id", "status"),
        Index("ix_tonpays_status", "status"),
    )

    # Random id in a range that never overlaps crypto order ids, so direct-pay can link it the same way.
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    order_id: Mapped[str] = mapped_column(String(20), nullable=False)
    invoice_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mode: Mapped[str] = mapped_column(String(10), nullable=False, default="standard")
    source: Mapped[str] = mapped_column(String(10), nullable=False, default="bot")
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    final_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    credited_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    invoice_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    web_invoice_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    card_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    card_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    receipt_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    paid_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
