"""add usage, rate and period detail to reseller billing rows

Revision ID: d7f2c8e4a1b6
Revises: b4e7d2a9c1f3
Create Date: 2026-10-09 18:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d7f2c8e4a1b6"
down_revision: str | None = "b4e7d2a9c1f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # All nullable: existing rows keep their values; the ledger derives their detail on read.
    op.add_column("reseller_billing_snapshots", sa.Column("used_bytes", sa.BigInteger(), nullable=True))
    op.add_column("reseller_billing_snapshots", sa.Column("unit_price", sa.Float(), nullable=True))
    op.add_column("reseller_billing_snapshots", sa.Column("period_start", sa.BigInteger(), nullable=True))
    op.add_column("reseller_billing_snapshots", sa.Column("is_debt", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("reseller_billing_snapshots", "is_debt")
    op.drop_column("reseller_billing_snapshots", "period_start")
    op.drop_column("reseller_billing_snapshots", "unit_price")
    op.drop_column("reseller_billing_snapshots", "used_bytes")
