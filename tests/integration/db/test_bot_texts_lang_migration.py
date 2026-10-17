"""The bot_texts migration swaps UNIQUE(key) for UNIQUE(key, lang) and backfills missing languages on SQLite."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest
import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext

_MIGRATION = (
    Path(__file__).resolve().parents[3]
    / "app"
    / "db"
    / "migrations"
    / "versions"
    / "24c2063023ee_bot_texts_unique_key_lang.py"
)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("bot_texts_lang_migration", _MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(engine: sa.Engine, direction: str) -> None:
    module = _load()
    with engine.begin() as conn, Operations.context(MigrationContext.configure(conn)):
        getattr(module, direction)()


@pytest.fixture
def engine(tmp_path):
    # Same shape as the init migration: an unnamed UNIQUE(key).
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    metadata = sa.MetaData()
    sa.Table(
        "bot_texts",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("lang", sa.String(10), nullable=True),
        sa.Column("banner_url", sa.String(500), nullable=True),
        sa.Column("banner_position", sa.String(10), nullable=True),
        sa.UniqueConstraint("key"),
    )
    metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO bot_texts (id, key, value, lang) VALUES "
                "(1, 'start_message', 'salam', NULL), (2, 'help_message', 'komak', ''), (3, 'info', 'hi', 'en')"
            )
        )
    yield engine
    engine.dispose()


def _uniques(engine: sa.Engine) -> list[list[str]]:
    return sorted(uc["column_names"] for uc in sa.inspect(engine).get_unique_constraints("bot_texts"))


def _rows(engine: sa.Engine) -> list[tuple]:
    with engine.connect() as conn:
        return [tuple(row) for row in conn.execute(sa.text("SELECT id, key, value, lang FROM bot_texts ORDER BY id"))]


def test_upgrade_backfills_lang_and_allows_one_row_per_language(engine: sa.Engine) -> None:
    _run(engine, "upgrade")
    _run(engine, "upgrade")

    assert _uniques(engine) == [["key", "lang"]]
    assert _rows(engine) == [
        (1, "start_message", "salam", "fa"),
        (2, "help_message", "komak", "fa"),
        (3, "info", "hi", "en"),
    ]
    with engine.begin() as conn:
        conn.execute(sa.text("INSERT INTO bot_texts (key, value, lang) VALUES ('start_message', 'hello', 'en')"))
    with pytest.raises(sa.exc.IntegrityError), engine.begin() as conn:
        conn.execute(sa.text("INSERT INTO bot_texts (key, value, lang) VALUES ('start_message', 'again', 'fa')"))
    with pytest.raises(sa.exc.IntegrityError), engine.begin() as conn:
        conn.execute(sa.text("INSERT INTO bot_texts (key, value, lang) VALUES ('start_message', 'null', NULL)"))


def test_upgrade_defaults_missing_lang_so_a_key_cannot_repeat(engine: sa.Engine) -> None:
    _run(engine, "upgrade")

    with engine.begin() as conn:
        conn.execute(sa.text("INSERT INTO bot_texts (key, value) VALUES ('new_key', 'a')"))
    with pytest.raises(sa.exc.IntegrityError), engine.begin() as conn:
        conn.execute(sa.text("INSERT INTO bot_texts (key, value) VALUES ('new_key', 'b')"))
    assert _rows(engine)[-1][1:] == ("new_key", "a", "fa")


def test_downgrade_keeps_default_language_row_and_restores_unique_key(engine: sa.Engine) -> None:
    _run(engine, "upgrade")
    with engine.begin() as conn:
        conn.execute(sa.text("INSERT INTO bot_texts (id, key, value, lang) VALUES (4, 'start_message', 'hello', 'en')"))
    _run(engine, "downgrade")
    _run(engine, "downgrade")

    assert _uniques(engine) == [["key"]]
    assert next(c["nullable"] for c in sa.inspect(engine).get_columns("bot_texts") if c["name"] == "lang")
    assert [row[0] for row in _rows(engine)] == [1, 2, 3]
