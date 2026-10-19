from sqlalchemy import BigInteger, Index, Integer, String, Text
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Packs and backups hold whole texts (up to 8 KB each), more than MySQL's 64 KB TEXT.
LargeText = Text().with_variant(LONGTEXT(), "mysql", "mariadb")


class ThemePack(Base):
    """A saved theme pack in the admin's library (see services/theme_pack.py for the data layout)."""

    __tablename__ = "theme_packs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # The pack JSON itself, exactly what an export file contains.
    data: Mapped[str] = mapped_column(LargeText, nullable=False)
    # Bot the pack was first made on ("pasarguard", "marzban", ...), from the pack's source block.
    source_bot: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)

    def __repr__(self):
        return f"<ThemePack(id={self.id}, name='{self.name}')>"


class ThemePackImport(Base):
    """One applied pack (from the library or a file) and the state it replaced, so it can be undone."""

    __tablename__ = "theme_pack_imports"
    __table_args__ = (Index("ix_theme_pack_imports_created", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Library pack that was applied; null for a pack applied straight from a file.
    pack_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    pack_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # "merge" keeps everything the pack does not mention, "replace" resets it to the defaults.
    mode: Mapped[str] = mapped_column(String(10), nullable=False, default="merge", server_default="merge")
    # JSON: {"texts": n, "buttons": n, "layout": bool, "reset": n}
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # JSON snapshot of every row the apply touched, as it was before.
    backup: Mapped[str] = mapped_column(LargeText, nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    restored_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    def __repr__(self):
        return f"<ThemePackImport(id={self.id}, pack_name='{self.pack_name}', restored_at={self.restored_at})>"
