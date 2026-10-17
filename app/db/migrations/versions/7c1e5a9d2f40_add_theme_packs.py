"""add theme_packs (pack library) and theme_pack_imports (undo snapshots)

Revision ID: 7c1e5a9d2f40
Revises: 24c2063023ee
Create Date: 2026-10-17 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "7c1e5a9d2f40"
down_revision: str | None = "24c2063023ee"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PACKS = "theme_packs"
IMPORTS = "theme_pack_imports"


def _large_text() -> sa.types.TypeEngine:
    return sa.Text().with_variant(mysql.LONGTEXT(), "mysql", "mariadb")


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if PACKS not in tables:
        op.create_table(
            PACKS,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("data", _large_text(), nullable=False),
            sa.Column("source_bot", sa.String(length=40), nullable=True),
            sa.Column("created_by", sa.BigInteger(), nullable=True),
            sa.Column("created_at", sa.BigInteger(), nullable=False),
            sa.Column("updated_at", sa.BigInteger(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    if IMPORTS not in tables:
        op.create_table(
            IMPORTS,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("pack_id", sa.Integer(), nullable=True),
            sa.Column("actor_id", sa.BigInteger(), nullable=True),
            sa.Column("pack_name", sa.String(length=100), nullable=True),
            sa.Column("mode", sa.String(length=10), nullable=False, server_default="merge"),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("backup", _large_text(), nullable=False),
            sa.Column("created_at", sa.BigInteger(), nullable=False),
            sa.Column("restored_at", sa.BigInteger(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_theme_pack_imports_created", IMPORTS, ["created_at"])


def downgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if IMPORTS in tables:
        op.drop_index("ix_theme_pack_imports_created", table_name=IMPORTS)
        op.drop_table(IMPORTS)
    if PACKS in tables:
        op.drop_table(PACKS)
