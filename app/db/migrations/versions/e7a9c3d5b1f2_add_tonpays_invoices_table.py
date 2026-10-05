"""add tonpays invoices table

Revision ID: e7a9c3d5b1f2
Revises: d8e1f4a2b6c7
Create Date: 2026-10-04 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7a9c3d5b1f2"
down_revision: str | None = "d8e1f4a2b6c7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "tonpays_invoices"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if TABLE not in existing_tables:
        op.create_table(
            TABLE,
            sa.Column("id", sa.BigInteger(), autoincrement=False, nullable=False),
            sa.Column("order_id", sa.String(length=20), nullable=False),
            sa.Column("invoice_id", sa.String(length=64), nullable=True),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("mode", sa.String(length=10), nullable=False, server_default="standard"),
            sa.Column("source", sa.String(length=10), nullable=False, server_default="bot"),
            sa.Column("amount", sa.BigInteger(), nullable=False),
            sa.Column("final_amount", sa.BigInteger(), nullable=True),
            sa.Column("credited_amount", sa.BigInteger(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("invoice_url", sa.Text(), nullable=True),
            sa.Column("web_invoice_url", sa.Text(), nullable=True),
            sa.Column("card_number", sa.String(length=64), nullable=True),
            sa.Column("card_name", sa.String(length=128), nullable=True),
            sa.Column("receipt_sent", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("message_id", sa.BigInteger(), nullable=True),
            sa.Column("created_at", sa.BigInteger(), nullable=False),
            sa.Column("updated_at", sa.BigInteger(), nullable=True),
            sa.Column("paid_at", sa.BigInteger(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

    existing_indexes = {ix["name"] for ix in inspector.get_indexes(TABLE)} if TABLE in existing_tables else set()
    if "ix_tonpays_order_id" not in existing_indexes:
        op.create_index("ix_tonpays_order_id", TABLE, ["order_id"], unique=True)
    if "ix_tonpays_invoice_id" not in existing_indexes:
        op.create_index("ix_tonpays_invoice_id", TABLE, ["invoice_id"])
    if "ix_tonpays_user_status" not in existing_indexes:
        op.create_index("ix_tonpays_user_status", TABLE, ["user_id", "status"])
    if "ix_tonpays_status" not in existing_indexes:
        op.create_index("ix_tonpays_status", TABLE, ["status"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE not in inspector.get_table_names():
        return
    existing_indexes = {ix["name"] for ix in inspector.get_indexes(TABLE)}
    for name in ("ix_tonpays_status", "ix_tonpays_user_status", "ix_tonpays_invoice_id", "ix_tonpays_order_id"):
        if name in existing_indexes:
            op.drop_index(name, table_name=TABLE)
    op.drop_table(TABLE)
