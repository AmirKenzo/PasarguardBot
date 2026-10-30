"""The bot reseller migration creates and drops its tables, and is safe to run twice."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext

_MIGRATION = (
    Path(__file__).resolve().parents[3] / "app" / "db" / "migrations" / "versions" / "b8e4d1f6c2a9_add_bot_resellers.py"
)
_TABLES = {
    "bot_reseller_services",
    "bot_resellers",
    "bot_reseller_grants",
    "bot_reseller_users",
    "bot_reseller_usage_hourly",
}


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("bot_resellers_migration", _MIGRATION)
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
    assert set(sa.inspect(engine).get_table_names()) >= _TABLES
    columns = {col["name"] for col in sa.inspect(engine).get_columns("bot_reseller_users")}
    assert {"baseline_bytes", "disabled_by", "deleted_at", "panel_user_id"} <= columns
    reseller_columns = {col["name"] for col in sa.inspect(engine).get_columns("bot_resellers")}
    assert {"username_prefix", "username_suffix"} <= reseller_columns
    _run(engine, "downgrade")
    assert not _TABLES & set(sa.inspect(engine).get_table_names())
