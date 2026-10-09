"""store the billed panel usage counter on the reseller account

Revision ID: a5e2c7f9d3b1
Revises: d7f2c8e4a1b6
Create Date: 2026-10-09 21:00:00.000000

"""

from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a5e2c7f9d3b1"
down_revision: str | None = "d7f2c8e4a1b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _state_counter(raw: str | None) -> int | None:
    try:
        data = json.loads(raw) if raw else {}
    except TypeError, ValueError:
        return None
    value = data.get("last_used_traffic") if isinstance(data, dict) else None
    return int(value) if value is not None else None


def upgrade() -> None:
    op.add_column("reseller_accounts", sa.Column("billed_traffic", sa.BigInteger(), nullable=True))

    # Seed usage accounts from what was billed so far: the latest usage ledger row, else the
    # counter kept in billing_state. Accounts with neither stay NULL and start from 0, as before.
    bind = op.get_bind()
    accounts = bind.execute(
        sa.text("SELECT code, billing_state FROM reseller_accounts WHERE pricing_mode = 'usage'")
    ).fetchall()
    for code, billing_state in accounts:
        row = bind.execute(
            sa.text(
                "SELECT used_traffic FROM reseller_billing_snapshots "
                "WHERE account_code = :code AND billed_minutes IS NULL "
                "ORDER BY snapshot_at DESC, id DESC LIMIT 1"
            ),
            {"code": code},
        ).first()
        counter = int(row[0]) if row and row[0] is not None else _state_counter(billing_state)
        if counter is not None:
            bind.execute(
                sa.text("UPDATE reseller_accounts SET billed_traffic = :value WHERE code = :code"),
                {"value": counter, "code": code},
            )


def downgrade() -> None:
    op.drop_column("reseller_accounts", "billed_traffic")
