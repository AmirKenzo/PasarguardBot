from sqlalchemy import BigInteger, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ResellerEvent(Base):
    """Reseller activity history (purchase, pause, suspend, renew, ...) shown in the web app and admin panel.

    Rows outlive the account (``account_code`` is not a foreign key) so deleted resellers keep their history.
    """

    __tablename__ = "reseller_events"
    __table_args__ = (
        Index("ix_reseller_events_account", "account_code", "created_at"),
        Index("ix_reseller_events_user", "telegram_id", "created_at"),
        Index("ix_reseller_events_created", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reseller_type: Mapped[str] = mapped_column(String(20), nullable=False, default="panel")
    account_code: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    actor_role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    data: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
