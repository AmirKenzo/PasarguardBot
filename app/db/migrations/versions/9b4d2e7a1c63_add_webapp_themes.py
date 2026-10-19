"""add webapp_themes (custom web app color themes)

Revision ID: 9b4d2e7a1c63
Revises: 7c1e5a9d2f40
Create Date: 2026-10-17 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9b4d2e7a1c63"
down_revision: str | None = "7c1e5a9d2f40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

THEMES = "webapp_themes"


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if THEMES not in tables:
        op.create_table(
            THEMES,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("data", sa.Text(), nullable=False),
            sa.Column("source_bot", sa.String(length=40), nullable=True),
            sa.Column("imported", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_by", sa.BigInteger(), nullable=True),
            sa.Column("created_at", sa.BigInteger(), nullable=False),
            sa.Column("updated_at", sa.BigInteger(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )


def downgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if THEMES in tables:
        op.drop_table(THEMES)
