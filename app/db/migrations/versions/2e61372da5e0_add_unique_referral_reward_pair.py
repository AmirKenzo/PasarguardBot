"""add unique referral reward pair

Revision ID: 2e61372da5e0
Revises: e7a9c3d5b1f2
Create Date: 2026-10-08 08:57:01.471105

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2e61372da5e0"
down_revision: str | None = "e7a9c3d5b1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "referral_rewards"
INDEX = "uq_refrewards_pair"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE not in inspector.get_table_names():
        return
    if INDEX in {ix["name"] for ix in inspector.get_indexes(TABLE)}:
        return

    # Keep the first reward per pair so the unique index can be created. The derived table
    # lets MySQL delete from the table it reads.
    op.execute(
        sa.text(
            f"DELETE FROM {TABLE} WHERE id NOT IN ("
            f"SELECT keep_id FROM (SELECT MIN(id) AS keep_id FROM {TABLE} "
            "GROUP BY referrer_id, referred_id) AS keep_rows)"
        )
    )
    op.create_index(INDEX, TABLE, ["referrer_id", "referred_id"], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE not in inspector.get_table_names():
        return
    if INDEX in {ix["name"] for ix in inspector.get_indexes(TABLE)}:
        op.drop_index(INDEX, table_name=TABLE)
