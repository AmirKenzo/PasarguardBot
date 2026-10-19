"""The crypto tx_hash migration adds a nullable, unique column and removes it again on SQLite."""

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
    / "b9e3f7a1c5d2_add_crypto_tx_hash.py"
)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("crypto_tx_hash_migration", _MIGRATION)
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
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    metadata = sa.MetaData()
    sa.Table(
        "cryptopayments",
        metadata,
        sa.Column("order_id", sa.Integer, primary_key=True),
        sa.Column("status", sa.String(50)),
        sa.Column("amount", sa.String(50), nullable=False),
    )
    metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(sa.text("INSERT INTO cryptopayments (order_id, status, amount) VALUES (1, 'Paid', '1.5')"))
    yield engine
    engine.dispose()


def _columns(engine: sa.Engine) -> set[str]:
    return {col["name"] for col in sa.inspect(engine).get_columns("cryptopayments")}


def _unique_indexes(engine: sa.Engine) -> dict[str, list[str]]:
    return {ix["name"]: ix["column_names"] for ix in sa.inspect(engine).get_indexes("cryptopayments") if ix["unique"]}


def test_upgrade_adds_unique_tx_hash_and_is_idempotent(engine: sa.Engine) -> None:
    _run(engine, "upgrade")
    _run(engine, "upgrade")

    assert "tx_hash" in _columns(engine)
    assert _unique_indexes(engine) == {"uq_crypto_tx_hash": ["tx_hash"]}
    with engine.begin() as conn:
        assert conn.execute(sa.text("SELECT tx_hash FROM cryptopayments WHERE order_id = 1")).scalar() is None
        conn.execute(sa.text("INSERT INTO cryptopayments (order_id, amount) VALUES (2, '2'), (3, '3')"))
        conn.execute(sa.text("UPDATE cryptopayments SET tx_hash = 'h' WHERE order_id = 2"))
    with pytest.raises(sa.exc.IntegrityError), engine.begin() as conn:
        conn.execute(sa.text("UPDATE cryptopayments SET tx_hash = 'h' WHERE order_id = 3"))


def test_downgrade_drops_index_and_column(engine: sa.Engine) -> None:
    _run(engine, "upgrade")
    _run(engine, "downgrade")
    _run(engine, "downgrade")

    assert "tx_hash" not in _columns(engine)
    assert _unique_indexes(engine) == {}
    with engine.connect() as conn:
        assert conn.execute(sa.text("SELECT amount FROM cryptopayments WHERE order_id = 1")).scalar() == "1.5"
