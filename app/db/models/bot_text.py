from sqlalchemy import BigInteger, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.i18n import DEFAULT_LANGUAGE


class BotText(Base):
    """An admin override of a bot text; one row per (key, lang)."""

    __tablename__ = "bot_texts"
    __table_args__ = (UniqueConstraint("key", "lang", name="uq_bot_texts_key_lang"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    # Not null: NULLs never collide in the unique constraint, so one key could repeat.
    lang: Mapped[str] = mapped_column(
        String(10), nullable=False, default=DEFAULT_LANGUAGE, server_default=DEFAULT_LANGUAGE
    )
    banner_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    banner_position: Mapped[str | None] = mapped_column(String(10), nullable=True)
