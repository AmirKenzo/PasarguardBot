"""CRUD for the ForApp bank-deposit ledger (idempotent SMS store)."""

from __future__ import annotations

import time

from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.future import select

from app.db.base import DATABASE_DIALECT, AsyncSessionLocal as Session
from app.db.models.bank_deposit import BankDeposit


def _upsert_insert():
    if DATABASE_DIALECT == "postgresql":
        return pg_insert(BankDeposit)
    if DATABASE_DIALECT == "mysql":
        return mysql_insert(BankDeposit)
    return sqlite_insert(BankDeposit)


# Columns never overwritten by a redelivery: first-seen match outcome wins.
_UPSERT_KEEP_ON_CONFLICT = ("id", "created_at", "status", "matched_tx_id", "matched_user_id")


def build_bank_deposit_upsert(values: dict):
    """Build the dialect-correct idempotent upsert statement (pure, testable).

    MySQL uses ``ON DUPLICATE KEY UPDATE``; PostgreSQL/SQLite use
    ``ON CONFLICT(id) DO UPDATE``.
    """
    stmt = _upsert_insert().values(**values)
    if DATABASE_DIALECT == "mysql":
        return stmt.on_duplicate_key_update(
            **{k: v for k, v in values.items() if k not in _UPSERT_KEEP_ON_CONFLICT}
        )
    update_cols = {k: getattr(stmt.excluded, k) for k in values if k not in _UPSERT_KEEP_ON_CONFLICT}
    return stmt.on_conflict_do_update(index_elements=["id"], set_=update_cols)


class BankDepositCRUD:
    async def upsert(
        self,
        *,
        deposit_id: str,
        raw_amount=None,
        amount_toman=None,
        unit=None,
        sender=None,
        bank=None,
        body=None,
        is_deposit: bool = True,
        received_at_ms=None,
        device=None,
        attempt: int = 1,
        is_test: bool = False,
    ) -> BankDeposit | None:
        now = int(time.time())
        values = {
            "id": deposit_id,
            "raw_amount": int(raw_amount) if raw_amount is not None else None,
            "amount_toman": int(amount_toman) if amount_toman is not None else None,
            "unit": unit,
            "sender": sender,
            "bank": bank,
            "body": body,
            "is_deposit": bool(is_deposit),
            "received_at_ms": int(received_at_ms) if received_at_ms else None,
            "device": device,
            "attempt": int(attempt or 1),
            "is_test": bool(is_test),
            "created_at": now,
        }
        async with Session() as session:
            await session.execute(build_bank_deposit_upsert(values))
            await session.commit()
            result = await session.execute(select(BankDeposit).where(BankDeposit.id == deposit_id))
            return result.scalar_one_or_none()

    async def get(self, deposit_id: str) -> BankDeposit | None:
        async with Session() as session:
            result = await session.execute(select(BankDeposit).where(BankDeposit.id == deposit_id))
            return result.scalar_one_or_none()

    async def mark_matched(self, deposit_id: str, *, tx_id: int, user_id: int) -> None:
        async with Session() as session:
            result = await session.execute(select(BankDeposit).where(BankDeposit.id == deposit_id))
            row = result.scalar_one_or_none()
            if row:
                row.status = "matched"
                row.matched_tx_id = int(tx_id)
                row.matched_user_id = int(user_id)
                await session.commit()

    async def mark_status(self, deposit_id: str, status: str) -> None:
        async with Session() as session:
            result = await session.execute(select(BankDeposit).where(BankDeposit.id == deposit_id))
            row = result.scalar_one_or_none()
            if row:
                row.status = status
                await session.commit()

    async def recent(self, limit: int = 50):
        async with Session() as session:
            result = await session.execute(
                select(BankDeposit).order_by(BankDeposit.created_at.desc()).limit(int(limit))
            )
            return result.scalars().all()
