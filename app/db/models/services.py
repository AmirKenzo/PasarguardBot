from sqlalchemy import BigInteger, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Service(Base):
    __tablename__ = "services"
    __table_args__ = (
        Index("ix_services_id", "id"),
        Index("ix_services_panel_expiry", "in_panel", "expiration_time"),
        Index("ix_services_panel_username", "in_panel", "username"),
    )

    code: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str] = mapped_column(String(64))

    enable: Mapped[bool] = mapped_column(default=False)
    in_panel: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    panel_userid: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    package_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    createtime: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    expiration_time: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    warning: Mapped[int] = mapped_column(default=0)
    warning_time: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    low_volume_notified: Mapped[bool] = mapped_column(default=False)
    expire_notified: Mapped[bool] = mapped_column(default=False)
    data_limit_reset_strategy: Mapped[str] = mapped_column(String(20), default="no_reset")
    ip_limit: Mapped[int] = mapped_column(default=0)  # 0 means unlimited, otherwise the user limit
    is_test: Mapped[bool | None] = mapped_column(default=None, nullable=True)  # True=test, False/null=paid
