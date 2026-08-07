from sqlalchemy import BigInteger, Boolean, Column, Index, Integer, String

from app.db.base import Base


class User(Base):
    __tablename__ = "user"
    __table_args__ = (
        Index("ix_user_number", "number"),
        Index("ix_user_ref", "ref"),
        Index("ix_user_time_s", "time_s"),
        Index("ix_user_status", "status"),
    )

    id = Column(BigInteger, primary_key=True)
    status = Column(String(50), nullable=True)
    time_s = Column(BigInteger, nullable=True)
    ref = Column(BigInteger, nullable=True)
    number = Column(String(20), nullable=True)
    amount = Column(BigInteger, nullable=True, default=0)
    invite = Column(Integer, nullable=True, default=0)
    tested = Column(Boolean, default=False)
    page = Column(Integer, nullable=True)
    language = Column(String(5), nullable=False, server_default="fa")
    last_dice_roll = Column(BigInteger, nullable=True)
    current_game_data = Column(String(100), nullable=True)
    show_volume = Column(Boolean, nullable=False, server_default="1")
    show_panel = Column(Boolean, nullable=False, server_default="1")
    show_service_word = Column(Boolean, nullable=False, server_default="1")
    show_config_name = Column(Boolean, nullable=False, server_default="0")
    service_buttons_per_row = Column(Integer, nullable=False, server_default="1")
    service_button_rows = Column(Integer, nullable=False, server_default="5")
    safe_mode = Column(Boolean, nullable=True)

    def __repr__(self):
        return f"<User(id={self.id}, status='{self.status}', time_s={self.time_s}, number={self.number}, amount={self.amount})>"
