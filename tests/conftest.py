"""Suite-wide setup.

Layout:
  tests/unit/         fast tests, no database or network; mirrors the ``app/`` tree
  tests/integration/  tests against an in-memory SQLite database
  tests/support/      helpers shared by tests (not collected)

Run one layer with ``pytest tests/unit`` or ``pytest -m integration``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_ENV_PATH = _ROOT / ".env"
_CREATED_TEST_ENV = False

_MINIMAL_ENV = """\
API_ID=1
API_HASH=testhash
BOT_TOKEN=1:test
ADMIN_ID=1
SQLALCHEMY_DATABASE_URL=sqlite+aiosqlite:///:memory:
"""

_LAYER_MARKERS = {"unit": pytest.mark.unit, "integration": pytest.mark.integration}


def pytest_configure(config: pytest.Config) -> None:
    """Ensure a minimal .env exists so `import app` can load config during tests."""
    global _CREATED_TEST_ENV
    if not _ENV_PATH.exists():
        _ENV_PATH.write_text(_MINIMAL_ENV, encoding="utf-8")
        _CREATED_TEST_ENV = True


def pytest_unconfigure(config: pytest.Config) -> None:
    if _CREATED_TEST_ENV and _ENV_PATH.exists():
        _ENV_PATH.unlink(missing_ok=True)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Mark every test with its layer from the folder it lives in, so `-m unit` works without decorators."""
    tests_dir = Path(__file__).resolve().parent
    for item in items:
        try:
            layer = item.path.resolve().relative_to(tests_dir).parts[0]
        except ValueError:
            continue
        marker = _LAYER_MARKERS.get(layer)
        if marker is not None:
            item.add_marker(marker)
