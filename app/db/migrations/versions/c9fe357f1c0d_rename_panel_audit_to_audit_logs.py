"""rename panel_audit_logs to audit_logs, admin_* columns to actor_*

The audit trail is no longer web-panel-specific: other parts of the bot will
start writing to it too, so the table and its actor columns drop the
panel/admin-only naming.

Revision ID: c9fe357f1c0d
Revises: a4d7e2c1b908
Create Date: 2026-09-15 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9fe357f1c0d"
down_revision: str | None = "a4d7e2c1b908"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.rename_table("panel_audit_logs", "audit_logs")
    op.alter_column("audit_logs", "admin_id", new_column_name="actor_id")
    op.alter_column("audit_logs", "admin_username", new_column_name="actor_username")

    op.drop_index("ix_panel_audit_created", table_name="audit_logs")
    op.drop_index("ix_panel_audit_admin", table_name="audit_logs")
    op.create_index("ix_audit_created", "audit_logs", ["created_at"])
    op.create_index("ix_audit_actor", "audit_logs", ["actor_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_actor", table_name="audit_logs")
    op.drop_index("ix_audit_created", table_name="audit_logs")
    op.create_index("ix_panel_audit_admin", "audit_logs", ["actor_id"])
    op.create_index("ix_panel_audit_created", "audit_logs", ["created_at"])

    op.alter_column("audit_logs", "actor_username", new_column_name="admin_username")
    op.alter_column("audit_logs", "actor_id", new_column_name="admin_id")
    op.rename_table("audit_logs", "panel_audit_logs")
