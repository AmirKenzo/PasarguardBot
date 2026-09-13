from sqlalchemy import BigInteger, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PanelAuditLog(Base):
    """Record of admin actions performed through the web panel.

    Admins authenticate through the existing WebApp login, so there is no
    account table here — only the trail of what was changed and by whom.
    """

    __tablename__ = "panel_audit_logs"
    __table_args__ = (
        Index("ix_panel_audit_created", "created_at"),
        Index("ix_panel_audit_admin", "admin_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    admin_username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)

    def __repr__(self):
        return f"<PanelAuditLog(id={self.id}, action='{self.action}', admin_id={self.admin_id})>"
