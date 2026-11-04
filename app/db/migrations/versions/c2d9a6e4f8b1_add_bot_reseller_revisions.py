"""Add monotonic bot reseller observation and mutation revisions."""

import sqlalchemy as sa
from alembic import op

revision = "c2d9a6e4f8b1"
down_revision = "b8e4d1f6c2a9"
branch_labels = None
depends_on = None

COLUMNS = (("bot_resellers", "mutation_generation"), ("bot_reseller_users", "observation_revision"))


def upgrade() -> None:
    for table, name in COLUMNS:
        if name not in {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}:
            op.add_column(table, sa.Column(name, sa.BigInteger(), nullable=False, server_default="0"))


def downgrade() -> None:
    for table, name in reversed(COLUMNS):
        if name in {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}:
            op.drop_column(table, name)
