"""make bot_texts unique per key and lang (lang not null)

Revision ID: 24c2063023ee
Revises: b9e3f7a1c5d2
Create Date: 2026-10-17 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "24c2063023ee"
down_revision: str | None = "b9e3f7a1c5d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "bot_texts"
CONSTRAINT = "uq_bot_texts_key_lang"
KEY_CONSTRAINT = "uq_bot_texts_key"
DEFAULT_LANG = "fa"
# The init migration left UNIQUE(key) unnamed; on SQLite batch mode needs a name to drop it.
NAMING = {"uq": "uq_%(table_name)s_%(column_0_name)s"}

bot_texts = sa.table(TABLE, sa.column("lang", sa.String))


def _unique_names(inspector: sa.Inspector, columns: list[str]) -> list[str]:
    """Names of the unique constraints/indexes covering exactly `columns` (unnamed ones get KEY_CONSTRAINT)."""
    names: list[str] = []
    for uc in inspector.get_unique_constraints(TABLE):
        if uc["column_names"] == columns:
            names.append(uc["name"] or NAMING["uq"] % {"table_name": TABLE, "column_0_name": columns[0]})
    for ix in inspector.get_indexes(TABLE):
        if ix["unique"] and ix["column_names"] == columns and ix["name"] not in names:
            names.append(ix["name"])
    return names


def _lang_nullable(inspector: sa.Inspector) -> bool:
    return next(col["nullable"] for col in inspector.get_columns(TABLE) if col["name"] == "lang")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE not in inspector.get_table_names():
        return

    # Rows saved without a language were the Persian texts; give them the default so lookups by lang find them.
    op.execute(
        bot_texts.update().where(sa.or_(bot_texts.c.lang.is_(None), bot_texts.c.lang == "")).values(lang=DEFAULT_LANG)
    )

    key_only = _unique_names(inspector, ["key"])
    has_pair = bool(_unique_names(inspector, ["key", "lang"]))
    lang_nullable = _lang_nullable(inspector)
    if not key_only and has_pair and not lang_nullable:
        return
    with op.batch_alter_table(TABLE, naming_convention=NAMING) as batch_op:
        for name in key_only:
            batch_op.drop_constraint(name, type_="unique")
        # NULLs never collide in a unique constraint, so a nullable lang would let one key repeat.
        if lang_nullable:
            batch_op.alter_column(
                "lang",
                existing_type=sa.String(length=10),
                nullable=False,
                server_default=DEFAULT_LANG,
            )
        if not has_pair:
            batch_op.create_unique_constraint(CONSTRAINT, ["key", "lang"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE not in inspector.get_table_names():
        return

    # UNIQUE(key) can hold one row per key again: keep the default-language row where several exist.
    # The derived table lets MySQL delete from the table it reads.
    key = bind.dialect.identifier_preparer.quote("key")
    op.execute(
        sa.text(
            f"DELETE FROM {TABLE} WHERE (lang IS NULL OR lang <> :lang) AND {key} IN ("
            f"SELECT k FROM (SELECT {key} AS k FROM {TABLE} GROUP BY {key} HAVING COUNT(*) > 1) AS dup_keys)"
        ).bindparams(lang=DEFAULT_LANG)
    )

    pair = _unique_names(inspector, ["key", "lang"])
    has_key_only = bool(_unique_names(inspector, ["key"]))
    lang_nullable = _lang_nullable(inspector)
    if not pair and has_key_only and lang_nullable:
        return
    with op.batch_alter_table(TABLE, naming_convention=NAMING) as batch_op:
        for name in pair:
            batch_op.drop_constraint(name, type_="unique")
        if not lang_nullable:
            batch_op.alter_column(
                "lang",
                existing_type=sa.String(length=10),
                nullable=True,
                server_default=None,
            )
        if not has_key_only:
            batch_op.create_unique_constraint(KEY_CONSTRAINT, ["key"])
