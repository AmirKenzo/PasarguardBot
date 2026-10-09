"""Fixtures for the upgrade tests; the old install and its helpers live in ``old_install``.

``old_install`` imports ``app``, which needs the test ``.env`` the root conftest writes at configure
time, so it is imported inside the fixtures rather than at module load.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def old_engine(tmp_path):
    """A SQLite install with the schema and rows from before the two migrations."""
    from tests.integration.upgrade import old_install

    yield from old_install.old_engine_fixture(tmp_path)


@pytest.fixture
def migrated_db_path(tmp_path):
    """Path of an old install that went through both upgrades."""
    from tests.integration.upgrade import old_install

    return old_install.build_migrated_db(tmp_path)


@pytest.fixture
async def upgraded(monkeypatch: pytest.MonkeyPatch, migrated_db_path):
    """The upgraded install wired to the real services, with the panel faked and time frozen."""
    from tests.integration.upgrade import old_install

    async for env in old_install.upgraded_fixture(monkeypatch, migrated_db_path):
        yield env
