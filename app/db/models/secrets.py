from __future__ import annotations

from sqlalchemy import BigInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SECRET_CRYPTO_KEY = "crypto_key"
SECRET_WEBHOOK = "webhook_secret"
SECRET_NAMES: tuple[str, ...] = (SECRET_CRYPTO_KEY, SECRET_WEBHOOK)


class Secret(Base):
    __tablename__ = "secrets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
