"""add web panel audit log and home keyboard layout columns

Revision ID: a4d7e2c1b908
Revises: b1c2d3e4f5a6
Create Date: 2026-09-13 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a4d7e2c1b908"
down_revision: str | None = "b1c2d3e4f5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "panel_audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("admin_id", sa.BigInteger(), nullable=True),
        sa.Column("admin_username", sa.String(length=64), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=40), nullable=True),
        sa.Column("target_id", sa.String(length=64), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_panel_audit_created", "panel_audit_logs", ["created_at"])
    op.create_index("ix_panel_audit_admin", "panel_audit_logs", ["admin_id"])

    op.add_column("keyboard_buttons", sa.Column("sort_row", sa.Integer(), nullable=True))
    op.add_column("keyboard_buttons", sa.Column("sort_order", sa.Integer(), nullable=True))
    op.add_column(
        "keyboard_buttons",
        sa.Column("hidden", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("keyboard_buttons", "hidden")
    op.drop_column("keyboard_buttons", "sort_order")
    op.drop_column("keyboard_buttons", "sort_row")

    op.drop_index("ix_panel_audit_admin", table_name="panel_audit_logs")
    op.drop_index("ix_panel_audit_created", table_name="panel_audit_logs")
    op.drop_table("panel_audit_logs")
