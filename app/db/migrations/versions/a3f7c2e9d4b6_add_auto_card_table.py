"""add auto card table

Revision ID: a3f7c2e9d4b6
Revises: e2c6a9f4b8d1
Create Date: 2026-10-10 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3f7c2e9d4b6"
down_revision: str | None = "e2c6a9f4b8d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "auto_cart"
INDEXES = (
    ("ix_auto_cart_status_time", ["status", "time"]),
    ("ix_auto_cart_amount_status", ["amount", "status"]),
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if TABLE not in existing_tables:
        op.create_table(
            TABLE,
            sa.Column("code", sa.BigInteger(), autoincrement=False, nullable=False),
            sa.Column("time", sa.BigInteger(), nullable=False),
            sa.Column("amount", sa.BigInteger(), nullable=False),
            sa.Column("first_amount", sa.BigInteger(), nullable=False),
            sa.Column("id", sa.BigInteger(), nullable=False),
            sa.Column("status", sa.Boolean(), nullable=True),
            sa.Column("msg_id", sa.BigInteger(), nullable=True),
            sa.PrimaryKeyConstraint("code"),
        )

    existing_indexes = {ix["name"] for ix in inspector.get_indexes(TABLE)} if TABLE in existing_tables else set()
    for name, columns in INDEXES:
        if name not in existing_indexes:
            op.create_index(name, TABLE, columns, unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE not in inspector.get_table_names():
        return
    existing_indexes = {ix["name"] for ix in inspector.get_indexes(TABLE)}
    for name, _ in reversed(INDEXES):
        if name in existing_indexes:
            op.drop_index(name, table_name=TABLE)
    op.drop_table(TABLE)
