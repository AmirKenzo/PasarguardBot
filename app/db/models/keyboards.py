from sqlalchemy import BigInteger, Boolean, Integer, String, Text, false
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class KeyboardButton(Base):
    __tablename__ = "keyboard_buttons"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    button_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    button_text: Mapped[str] = mapped_column(Text, nullable=False)
    button_style: Mapped[str | None] = mapped_column(String(20), nullable=True)
    button_icon: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Home menu layout. Both null means "use the built-in layout".
    sort_row: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sort_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Admin switch: a hidden button is never shown, whatever the other conditions say.
    hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false(), default=False)

    def __repr__(self):
        return f"<KeyboardButton(id={self.id}, key='{self.button_key}', text='{self.button_text}')>"
