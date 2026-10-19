"""The web app themes migration creates and drops its table, and is safe to run twice."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext

_MIGRATION = (
    Path(__file__).resolve().parents[3] / "app" / "db" / "migrations" / "versions" / "9b4d2e7a1c63_add_webapp_themes.py"
)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("webapp_themes_migration", _MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(engine: sa.Engine, direction: str) -> None:
    module = _load()
    with engine.begin() as conn, Operations.context(MigrationContext.configure(conn)):
        getattr(module, direction)()


def test_upgrade_downgrade(tmp_path) -> None:
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'm.db'}")
    _run(engine, "upgrade")
    _run(engine, "upgrade")
    assert "webapp_themes" in set(sa.inspect(engine).get_table_names())
    columns = {col["name"] for col in sa.inspect(engine).get_columns("webapp_themes")}
    assert {"name", "data", "source_bot", "imported", "updated_at"} <= columns
    _run(engine, "downgrade")
    assert "webapp_themes" not in set(sa.inspect(engine).get_table_names())
