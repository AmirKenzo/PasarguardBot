"""add forapp bank deposits ledger + payable columns on transactions

Revision ID: f4a1c9d2e7b3
Revises: e2c6a9f4b8d1
Create Date: 2026-10-10 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f4a1c9d2e7b3"
down_revision: str | None = "e2c6a9f4b8d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "bank_deposits"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if TABLE not in existing_tables:
        op.create_table(
            TABLE,
            sa.Column("id", sa.String(length=128), nullable=False),
            sa.Column("raw_amount", sa.BigInteger(), nullable=True),
            sa.Column("amount_toman", sa.BigInteger(), nullable=True),
            sa.Column("unit", sa.String(length=16), nullable=True),
            sa.Column("sender", sa.String(length=64), nullable=True),
            sa.Column("bank", sa.String(length=64), nullable=True),
            sa.Column("body", sa.Text(), nullable=True),
            sa.Column("is_deposit", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("received_at_ms", sa.BigInteger(), nullable=True),
            sa.Column("device", sa.String(length=128), nullable=True),
            sa.Column("attempt", sa.BigInteger(), nullable=False, server_default="1"),
            sa.Column("is_test", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="unmatched"),
            sa.Column("matched_tx_id", sa.BigInteger(), nullable=True),
            sa.Column("matched_user_id", sa.BigInteger(), nullable=True),
            sa.Column("created_at", sa.BigInteger(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )

    existing_indexes = {ix["name"] for ix in inspector.get_indexes(TABLE)} if TABLE in inspector.get_table_names() else set()
    if "ix_bank_deposits_status" not in existing_indexes:
        op.create_index("ix_bank_deposits_status", TABLE, ["status"])
    if "ix_bank_deposits_amount" not in existing_indexes:
        op.create_index("ix_bank_deposits_amount", TABLE, ["amount_toman"])
    if "ix_bank_deposits_created" not in existing_indexes:
        op.create_index("ix_bank_deposits_created", TABLE, ["created_at"])

    tx_cols = {c["name"] for c in inspector.get_columns("transactions")} if "transactions" in existing_tables else set()
    if "transactions" in existing_tables:
        if "payable_amount" not in tx_cols:
            op.add_column("transactions", sa.Column("payable_amount", sa.BigInteger(), nullable=True))
        if "amount_offset" not in tx_cols:
            op.add_column("transactions", sa.Column("amount_offset", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE in inspector.get_table_names():
        existing_indexes = {ix["name"] for ix in inspector.get_indexes(TABLE)}
        for name in ("ix_bank_deposits_created", "ix_bank_deposits_amount", "ix_bank_deposits_status"):
            if name in existing_indexes:
                op.drop_index(name, table_name=TABLE)
        op.drop_table(TABLE)
    if "transactions" in inspector.get_table_names():
        tx_cols = {c["name"] for c in inspector.get_columns("transactions")}
        if "amount_offset" in tx_cols:
            op.drop_column("transactions", "amount_offset")
        if "payable_amount" in tx_cols:
            op.drop_column("transactions", "payable_amount")
