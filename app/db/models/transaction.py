from sqlalchemy import BigInteger, Column, Index, String

from app.db.base import Base


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_tx_user_method_status", "user_id", "method", "status"),
        Index("ix_tx_status_created", "status", "created_at"),
        Index("ix_tx_auto_approve_at", "auto_approve_at"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False)
    amount = Column(BigInteger, nullable=False)
    method = Column(String(20), nullable=False)  # manual or auto
    status = Column(String(20), nullable=False, default="pending")
    created_at = Column(BigInteger, nullable=False)
    completed_at = Column(BigInteger, nullable=True)
    message_id = Column(BigInteger, nullable=True)  # log channel message id
    message_chat_id = Column(BigInteger, nullable=True)
    auto_approve_at = Column(BigInteger, nullable=True)
    auto_approve_rule_id = Column(BigInteger, nullable=True)
