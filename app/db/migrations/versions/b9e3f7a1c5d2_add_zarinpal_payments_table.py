"""add zarinpal payments table

Revision ID: b9e3f7a1c5d2
Revises: c8d4f2a6e9b3
Create Date: 2026-10-10 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b9e3f7a1c5d2"
down_revision: str | None = "c8d4f2a6e9b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "zarinpal_payments"
INDEXES = (
    ("ix_zarinpal_order_id", ["order_id"], True),
    ("ix_zarinpal_authority", ["authority"], False),
    ("ix_zarinpal_user_status", ["user_id", "status"], False),
    ("ix_zarinpal_status", ["status"], False),
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if TABLE not in existing_tables:
        op.create_table(
            TABLE,
            sa.Column("id", sa.BigInteger(), autoincrement=False, nullable=False),
            sa.Column("order_id", sa.String(length=20), nullable=False),
            sa.Column("authority", sa.String(length=64), nullable=True),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("sandbox", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("source", sa.String(length=10), nullable=False, server_default="bot"),
            sa.Column("amount", sa.BigInteger(), nullable=False),
            sa.Column("credited_amount", sa.BigInteger(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("ref_id", sa.String(length=32), nullable=True),
            sa.Column("card_pan", sa.String(length=32), nullable=True),
            sa.Column("message_id", sa.BigInteger(), nullable=True),
            sa.Column("created_at", sa.BigInteger(), nullable=False),
            sa.Column("updated_at", sa.BigInteger(), nullable=True),
            sa.Column("paid_at", sa.BigInteger(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

    existing_indexes = {ix["name"] for ix in inspector.get_indexes(TABLE)} if TABLE in existing_tables else set()
    for name, columns, unique in INDEXES:
        if name not in existing_indexes:
            op.create_index(name, TABLE, columns, unique=unique)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE not in inspector.get_table_names():
        return
    existing_indexes = {ix["name"] for ix in inspector.get_indexes(TABLE)}
    for name, _, _ in reversed(INDEXES):
        if name in existing_indexes:
            op.drop_index(name, table_name=TABLE)
    op.drop_table(TABLE)
