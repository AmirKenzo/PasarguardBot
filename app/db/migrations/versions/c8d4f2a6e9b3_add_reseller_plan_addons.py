"""add reseller plan add-on prices and per-account extra user slots

Revision ID: c8d4f2a6e9b3
Revises: a5e2c7f9d3b1
Create Date: 2026-10-10 10:00:00.000000

"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c8d4f2a6e9b3"
down_revision: str | None = "a5e2c7f9d3b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


DEFAULT_USER_PRICE = 2000


def _panel_user_price(raw) -> int:
    """The panel-wide extra-user price that plans now carry themselves; 0 when it was switched off."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return 0
    capacity = raw.get("reseller_user_capacity") if isinstance(raw, dict) else None
    if not isinstance(capacity, dict) or not capacity.get("enabled"):
        return 0
    try:
        price = capacity.get("price_per_user", DEFAULT_USER_PRICE)
        return max(0, int(price if price is not None else DEFAULT_USER_PRICE))
    except TypeError, ValueError:
        return 0


def upgrade() -> None:
    for column in ("addon_day_price", "addon_gb_price", "addon_user_price"):
        op.add_column(
            "reseller_plans", sa.Column(column, sa.Float(), nullable=False, server_default=sa.text("0"))
        )
    op.add_column("reseller_accounts", sa.Column("extra_users", sa.Integer(), nullable=True))

    bind = op.get_bind()
    for code, feature_settings in bind.execute(sa.text("SELECT code, feature_settings FROM panels")).fetchall():
        price = _panel_user_price(feature_settings)
        if price:
            bind.execute(
                sa.text("UPDATE reseller_plans SET addon_user_price = :price WHERE panel_code = :code"),
                {"price": price, "code": code},
            )

    rows = bind.execute(
        sa.text(
            "SELECT a.code, a.max_users, p.max_users FROM reseller_accounts a "
            "JOIN reseller_plans p ON p.id = a.plan_id"
        )
    ).fetchall()
    for code, account_max, plan_max in rows:
        account_max, plan_max = int(account_max or 0), int(plan_max or 0)
        if account_max > 0 and plan_max > 0 and account_max > plan_max:
            bind.execute(
                sa.text("UPDATE reseller_accounts SET extra_users = :extra WHERE code = :code"),
                {"extra": account_max - plan_max, "code": code},
            )


def downgrade() -> None:
    op.drop_column("reseller_accounts", "extra_users")
    for column in ("addon_user_price", "addon_gb_price", "addon_day_price"):
        op.drop_column("reseller_plans", column)
