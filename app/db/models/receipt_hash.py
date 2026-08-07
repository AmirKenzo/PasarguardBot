from sqlalchemy import BigInteger, Column, Index, String

from app.db.base import Base


class ReceiptHash(Base):
    __tablename__ = "receipt_hashes"
    __table_args__ = (Index("ix_receipt_tx", "transaction_id"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    phash = Column(String(64), nullable=False, unique=True, index=True)
    transaction_id = Column(BigInteger, nullable=True)
    user_id = Column(BigInteger, nullable=False)
    created_at = Column(BigInteger, nullable=False)
