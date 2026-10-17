from sqlalchemy import BigInteger, Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WebappTheme(Base):
    """A custom web app color theme in the admin's library (see services/webapp_theme.py for the layout)."""

    __tablename__ = "webapp_themes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    data: Mapped[str] = mapped_column(Text, nullable=False)
    source_bot: Mapped[str | None] = mapped_column(String(40), nullable=True)
    imported: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)

    def __repr__(self):
        return f"<WebappTheme(id={self.id}, name='{self.name}')>"
