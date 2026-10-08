"""drop glass buttons mode

The global "glassy buttons" switch only wrapped the stored home-button labels in
brackets. It is gone, so labels it bracketed are restored and the key removed.
Buttons whose own style is "glass" keep their brackets.

Revision ID: f3b8a1d6c2e4
Revises: 2e61372da5e0
Create Date: 2026-10-09 12:00:00.000000

"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3b8a1d6c2e4"
down_revision: str | None = "2e61372da5e0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GLASS_LEFT = "「"
GLASS_RIGHT = "」"


def _load(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, (str, bytes)) and raw:
        try:
            data = json.loads(raw)
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {}
    return {}


def _unglass(label: str) -> str:
    text = (label or "").strip()
    if not (text.startswith(GLASS_LEFT) and text.endswith(GLASS_RIGHT)):
        return text
    return text[len(GLASS_LEFT) : -len(GLASS_RIGHT)].strip()


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "settings" not in tables:
        return

    was_on = False
    for row_id, raw in bind.execute(sa.text("SELECT id, core_settings FROM settings")).fetchall():
        core = _load(raw)
        if "glass_buttons_mode" not in core:
            continue
        was_on = was_on or bool(core.pop("glass_buttons_mode"))
        bind.execute(
            sa.text("UPDATE settings SET core_settings = :core WHERE id = :id"),
            {"core": json.dumps(core, ensure_ascii=False), "id": row_id},
        )

    if not was_on or "keyboard_buttons" not in tables:
        return

    rows = bind.execute(
        sa.text("SELECT id, button_text, button_style FROM keyboard_buttons WHERE button_key LIKE 'bt.menu_%'")
    ).fetchall()
    for row_id, text, style in rows:
        if style == "glass":
            continue
        plain = _unglass(text or "")
        if plain and plain != (text or ""):
            bind.execute(
                sa.text("UPDATE keyboard_buttons SET button_text = :text WHERE id = :id"),
                {"text": plain, "id": row_id},
            )


def downgrade() -> None:
    # The switch defaulted to off; nothing to restore.
    pass
