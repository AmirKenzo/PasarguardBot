import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext

MIGRATION = (
    Path(__file__).resolve().parents[3] / "app/db/migrations/versions" / "c2d9a6e4f8b1_add_bot_reseller_revisions.py"
)


def test_revision_migration_backfills_defaults_and_preserves_rows(tmp_path):
    spec = importlib.util.spec_from_file_location("reseller_revisions", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'revisions.db'}")
    metadata = sa.MetaData()
    for name in ("bot_resellers", "bot_reseller_users"):
        sa.Table(name, metadata, sa.Column("id", sa.Integer, primary_key=True))
    metadata.create_all(engine)
    with engine.begin() as conn:
        for table in metadata.tables.values():
            conn.execute(table.insert().values(id=1))
    for _ in range(2):
        with engine.begin() as conn, Operations.context(MigrationContext.configure(conn)):
            module.upgrade()
    with engine.begin() as conn:
        for table, column in (("bot_resellers", "mutation_generation"), ("bot_reseller_users", "observation_revision")):
            assert conn.execute(sa.text(f"SELECT id, {column} FROM {table}")).all() == [(1, 0)]
            conn.execute(sa.text(f"INSERT INTO {table} (id) VALUES (2)"))
            assert conn.execute(sa.text(f"SELECT {column} FROM {table} WHERE id=2")).scalar_one() == 0
    with engine.begin() as conn, Operations.context(MigrationContext.configure(conn)):
        module.downgrade()
    for table in metadata.tables:
        assert {c["name"] for c in sa.inspect(engine).get_columns(table)} == {"id"}
        with engine.connect() as conn:
            assert conn.execute(sa.text(f"SELECT id FROM {table} ORDER BY id")).all() == [(1,), (2,)]
    engine.dispose()
