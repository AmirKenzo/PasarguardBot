"""add reseller events and hourly billed minutes

Revision ID: b4e7d2a9c1f3
Revises: c5e8b1f4a2d6
Create Date: 2026-10-09 12:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4e7d2a9c1f3"
down_revision: str | None = "c5e8b1f4a2d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reseller_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("reseller_type", sa.String(length=20), server_default="panel", nullable=False),
        sa.Column("account_code", sa.BigInteger(), nullable=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=128), nullable=False),
        sa.Column("actor_id", sa.BigInteger(), nullable=True),
        sa.Column("actor_role", sa.String(length=32), nullable=True),
        sa.Column("data", sa.Text(), nullable=True),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reseller_events_account", "reseller_events", ["account_code", "created_at"], unique=False)
    op.create_index("ix_reseller_events_user", "reseller_events", ["telegram_id", "created_at"], unique=False)
    op.create_index("ix_reseller_events_created", "reseller_events", ["created_at"], unique=False)
    op.add_column("reseller_billing_snapshots", sa.Column("billed_minutes", sa.Integer(), nullable=True))
    op.create_index(
        "ix_reseller_snapshots_account_time",
        "reseller_billing_snapshots",
        ["account_code", "snapshot_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_reseller_snapshots_account_time", table_name="reseller_billing_snapshots")
    op.drop_column("reseller_billing_snapshots", "billed_minutes")
    op.drop_index("ix_reseller_events_created", table_name="reseller_events")
    op.drop_index("ix_reseller_events_user", table_name="reseller_events")
    op.drop_index("ix_reseller_events_account", table_name="reseller_events")
    op.drop_table("reseller_events")
