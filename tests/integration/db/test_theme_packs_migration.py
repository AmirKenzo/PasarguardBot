"""The theme packs migration creates and drops its two tables, and is safe to run twice."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext

_MIGRATION = (
    Path(__file__).resolve().parents[3] / "app" / "db" / "migrations" / "versions" / "7c1e5a9d2f40_add_theme_packs.py"
)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("theme_packs_migration", _MIGRATION)
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
    tables = set(sa.inspect(engine).get_table_names())
    assert {"theme_packs", "theme_pack_imports"} <= tables
    columns = {col["name"] for col in sa.inspect(engine).get_columns("theme_pack_imports")}
    assert {"pack_id", "mode", "backup", "restored_at"} <= columns
    _run(engine, "downgrade")
    assert not {"theme_packs", "theme_pack_imports"} & set(sa.inspect(engine).get_table_names())
