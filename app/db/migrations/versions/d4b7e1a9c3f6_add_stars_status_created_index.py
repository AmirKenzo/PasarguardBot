"""add stars status created index

Revision ID: d4b7e1a9c3f6
Revises: e2c6a9f4b8d1
Create Date: 2026-10-13 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4b7e1a9c3f6"
down_revision: str | None = "e2c6a9f4b8d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "stars_transactions"
INDEX = "ix_stars_status_created"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE not in inspector.get_table_names():
        return
    if INDEX in {ix["name"] for ix in inspector.get_indexes(TABLE)}:
        return
    op.create_index(INDEX, TABLE, ["status", "created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE not in inspector.get_table_names():
        return
    if INDEX in {ix["name"] for ix in inspector.get_indexes(TABLE)}:
        op.drop_index(INDEX, table_name=TABLE)
