"""add stars transactions table

Revision ID: d3a1f6c0b2e4
Revises: c9fe357f1c0d
Create Date: 2026-09-17 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d3a1f6c0b2e4"
down_revision: str | None = "c9fe357f1c0d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "stars_transactions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("invoice_no", sa.String(length=16), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("stars", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("paid_at", sa.BigInteger(), nullable=True),
        sa.Column("message_id", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stars_invoice_no", "stars_transactions", ["invoice_no"], unique=True)
    op.create_index("ix_stars_user_status", "stars_transactions", ["user_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_stars_user_status", table_name="stars_transactions")
    op.drop_index("ix_stars_invoice_no", table_name="stars_transactions")
    op.drop_table("stars_transactions")
