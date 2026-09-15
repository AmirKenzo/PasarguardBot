"""rename panel_audit_logs to audit_logs, admin_* columns to actor_*

The audit trail is no longer web-panel-specific: other parts of the bot will
start writing to it too, so the table and its actor columns drop the
panel/admin-only naming.

Revision ID: c9fe357f1c0d
Revises: a4d7e2c1b908
Create Date: 2026-09-15 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9fe357f1c0d"
down_revision: str | None = "a4d7e2c1b908"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    tables = sa.inspect(op.get_bind()).get_table_names()

    # Already on the new name (renamed already, or created directly under it)
    # — nothing to do.
    if "audit_logs" in tables:
        return

    if "panel_audit_logs" in tables:
        op.rename_table("panel_audit_logs", "audit_logs")
        op.alter_column("audit_logs", "admin_id", new_column_name="actor_id")
        op.alter_column("audit_logs", "admin_username", new_column_name="actor_username")
        op.drop_index("ix_panel_audit_created", table_name="audit_logs")
        op.drop_index("ix_panel_audit_admin", table_name="audit_logs")
        op.create_index("ix_audit_created", "audit_logs", ["created_at"])
        op.create_index("ix_audit_actor", "audit_logs", ["actor_id"])
        return

    # Neither name exists: this database's migration bookkeeping and its
    # actual tables have drifted apart (e.g. tables rebuilt out of band), so
    # the previous revision's create_table never really ran here. Create the
    # table directly in its final shape instead of leaving it missing.
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("actor_id", sa.BigInteger(), nullable=True),
        sa.Column("actor_username", sa.String(length=64), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=40), nullable=True),
        sa.Column("target_id", sa.String(length=64), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_created", "audit_logs", ["created_at"])
    op.create_index("ix_audit_actor", "audit_logs", ["actor_id"])


def downgrade() -> None:
    tables = sa.inspect(op.get_bind()).get_table_names()
    if "panel_audit_logs" in tables or "audit_logs" not in tables:
        return

    op.drop_index("ix_audit_actor", table_name="audit_logs")
    op.drop_index("ix_audit_created", table_name="audit_logs")
    op.create_index("ix_panel_audit_admin", "audit_logs", ["actor_id"])
    op.create_index("ix_panel_audit_created", "audit_logs", ["created_at"])

    op.alter_column("audit_logs", "actor_username", new_column_name="admin_username")
    op.alter_column("audit_logs", "actor_id", new_column_name="admin_id")
    op.rename_table("audit_logs", "panel_audit_logs")
