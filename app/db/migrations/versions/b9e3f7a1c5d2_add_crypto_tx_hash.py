"""add crypto tx hash

Revision ID: b9e3f7a1c5d2
Revises: d4b7e1a9c3f6
Create Date: 2026-10-13 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b9e3f7a1c5d2"
down_revision: str | None = "d4b7e1a9c3f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "cryptopayments"
COLUMN = "tx_hash"
INDEX = "uq_crypto_tx_hash"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE not in inspector.get_table_names():
        return
    if COLUMN not in {col["name"] for col in inspector.get_columns(TABLE)}:
        op.add_column(TABLE, sa.Column(COLUMN, sa.String(length=128), nullable=True))
    if INDEX not in {ix["name"] for ix in inspector.get_indexes(TABLE)}:
        op.create_index(INDEX, TABLE, [COLUMN], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE not in inspector.get_table_names():
        return
    if INDEX in {ix["name"] for ix in inspector.get_indexes(TABLE)}:
        op.drop_index(INDEX, table_name=TABLE)
    if COLUMN in {col["name"] for col in inspector.get_columns(TABLE)}:
        with op.batch_alter_table(TABLE) as batch_op:
            batch_op.drop_column(COLUMN)
