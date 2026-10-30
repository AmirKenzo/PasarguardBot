"""add bot reseller tables (services, resellers, grants, users, hourly usage)

Revision ID: b8e4d1f6c2a9
Revises: a3f7c2e9d4b6
Create Date: 2026-10-30 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8e4d1f6c2a9"
down_revision: str | None = "a3f7c2e9d4b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SERVICES = "bot_reseller_services"
RESELLERS = "bot_resellers"
GRANTS = "bot_reseller_grants"
USERS = "bot_reseller_users"
USAGE = "bot_reseller_usage_hourly"


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if SERVICES not in tables:
        op.create_table(
            SERVICES,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("panel_code", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=64), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("group_ids", sa.Text(), nullable=False),
            sa.Column("price_per_gb", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("sale_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("max_users", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("max_user_gb", sa.Float(), nullable=False, server_default="0"),
            sa.Column("max_user_days", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.BigInteger(), nullable=False),
            sa.Column("updated_at", sa.BigInteger(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    if RESELLERS not in tables:
        op.create_table(
            RESELLERS,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("telegram_id", sa.BigInteger(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
            sa.Column("username_prefix", sa.String(length=16), nullable=False),
            sa.Column("username_suffix", sa.String(length=16), nullable=False, server_default=""),
            sa.Column("carry", sa.Float(), nullable=False, server_default="0"),
            sa.Column("warned_hours", sa.Integer(), nullable=True),
            sa.Column("frozen_at", sa.BigInteger(), nullable=True),
            sa.Column("created_at", sa.BigInteger(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("telegram_id", name="uq_bot_reseller_tgid"),
        )
    if GRANTS not in tables:
        op.create_table(
            GRANTS,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("reseller_id", sa.Integer(), nullable=False),
            sa.Column("service_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("price_per_gb", sa.Integer(), nullable=True),
            sa.Column("max_users", sa.Integer(), nullable=True),
            sa.Column("max_user_gb", sa.Float(), nullable=True),
            sa.Column("max_user_days", sa.Integer(), nullable=True),
            sa.Column("reject_reason", sa.Text(), nullable=True),
            sa.Column("requested_at", sa.BigInteger(), nullable=False),
            sa.Column("decided_at", sa.BigInteger(), nullable=True),
            sa.Column("decided_by", sa.BigInteger(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("reseller_id", "service_id", name="uq_bot_reseller_grant"),
        )
        op.create_index("ix_bot_reseller_grant_status", GRANTS, ["status"])
    if USERS not in tables:
        op.create_table(
            USERS,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("reseller_id", sa.Integer(), nullable=False),
            sa.Column("service_id", sa.Integer(), nullable=False),
            sa.Column("panel_code", sa.Integer(), nullable=False),
            sa.Column("panel_user_id", sa.BigInteger(), nullable=False),
            sa.Column("username", sa.String(length=64), nullable=False),
            sa.Column("display_name", sa.String(length=48), nullable=False),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("baseline_bytes", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("disabled_by", sa.String(length=16), nullable=True),
            sa.Column("created_at", sa.BigInteger(), nullable=False),
            sa.Column("deleted_at", sa.BigInteger(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("panel_code", "panel_user_id", name="uq_bot_reseller_panel_user"),
        )
        op.create_index("ix_bot_reseller_user_owner", USERS, ["reseller_id", "deleted_at"])
    if USAGE not in tables:
        op.create_table(
            USAGE,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("reseller_id", sa.Integer(), nullable=False),
            sa.Column("service_id", sa.Integer(), nullable=False),
            sa.Column("hour", sa.BigInteger(), nullable=False),
            sa.Column("bytes", sa.BigInteger(), nullable=False, server_default="0"),
            sa.Column("amount", sa.Float(), nullable=False, server_default="0"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("reseller_id", "service_id", "hour", name="uq_bot_reseller_usage_hour"),
        )


def downgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    for table in (USAGE, USERS, GRANTS, RESELLERS, SERVICES):
        if table in tables:
            op.drop_table(table)
