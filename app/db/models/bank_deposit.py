from sqlalchemy import BigInteger, Boolean, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BankDeposit(Base):
    """Ledger of bank SMS deposits received via the ForApp Android webhook.

    Every POST is stored idempotently (PK = ForApp message id) before matching,
    so retries and duplicate deliveries never double-credit a user.
    """

    __tablename__ = "bank_deposits"
    __table_args__ = (
        Index("ix_bank_deposits_status", "status"),
        Index("ix_bank_deposits_amount", "amount_toman"),
        Index("ix_bank_deposits_created", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    raw_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    amount_toman: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(16), nullable=True)
    sender: Mapped[str | None] = mapped_column(String(64), nullable=True)
    bank: Mapped[str | None] = mapped_column(String(64), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_deposit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    received_at_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    device: Mapped[str | None] = mapped_column(String(128), nullable=True)
    attempt: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1)
    is_test: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="unmatched")
    matched_tx_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    matched_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
