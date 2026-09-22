"""Add API key login fields to user

Revision ID: d8e1f4a2b6c7
Revises: d3a1f6c0b2e4
Create Date: 2026-09-21 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d8e1f4a2b6c7"
down_revision: Union[str, None] = "d3a1f6c0b2e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("user", sa.Column("session_version", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("user", sa.Column("api_key_hash", sa.String(length=64), nullable=True))
    op.add_column("user", sa.Column("api_key_encrypted", sa.Text(), nullable=True))
    op.add_column("user", sa.Column("api_key_created_at", sa.BigInteger(), nullable=True))
    op.create_unique_constraint(None, "user", ["api_key_hash"])


def downgrade() -> None:
    op.drop_constraint(None, "user", type_="unique")
    op.drop_column("user", "api_key_created_at")
    op.drop_column("user", "api_key_encrypted")
    op.drop_column("user", "api_key_hash")
    op.drop_column("user", "session_version")
