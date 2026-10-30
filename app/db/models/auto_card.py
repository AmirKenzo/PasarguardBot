from sqlalchemy import BigInteger, Boolean, Column, Index

from app.db.base import Base


class AutoCard(Base):
    __tablename__ = "auto_cart"
    __table_args__ = (
        Index("ix_auto_cart_status_time", "status", "time"),
        Index("ix_auto_cart_amount_status", "amount", "status"),
    )

    code = Column(BigInteger, primary_key=True)
    time = Column(BigInteger, nullable=False)
    amount = Column(BigInteger, nullable=False)
    first_amount = Column(BigInteger, nullable=False)
    id = Column(BigInteger, nullable=False)
    status = Column(Boolean, default=False)
    msg_id = Column(BigInteger, nullable=True)
