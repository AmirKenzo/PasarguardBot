"""Focused tests for the owner-scoped Telegram service search."""

from __future__ import annotations

import importlib.util
import logging
import sys
import types
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _package(name: str) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__path__ = []
    return module


@pytest.fixture
def search_helpers(monkeypatch):
    module_name = "service_search_helpers_under_test"
    monkeypatch.delitem(sys.modules, module_name, raising=False)
    module = _load_module(
        module_name,
        PROJECT_ROOT / "app/telegram/user/services/search.py",
    )
    yield module
    sys.modules.pop(module_name, None)


@pytest_asyncio.fixture
async def service_db(monkeypatch):
    """Load the CRUD module against an isolated in-memory SQLite database."""
    base = declarative_base()

    for package_name in (
        "app",
        "app.db",
        "app.db.models",
        "app.db.crud",
        "app.utils",
        "app.utils.formatting",
    ):
        monkeypatch.setitem(sys.modules, package_name, _package(package_name))

    fake_base = types.ModuleType("app.db.base")
    fake_base.Base = base
    fake_base.AsyncSessionLocal = None
    monkeypatch.setitem(sys.modules, "app.db.base", fake_base)

    fake_panels = types.ModuleType("app.db.models.panels")
    fake_panels.Panels = type("Panels", (), {})
    monkeypatch.setitem(sys.modules, "app.db.models.panels", fake_panels)

    fake_logger = types.ModuleType("app.logger")
    fake_logger.get_logger = logging.getLogger
    monkeypatch.setitem(sys.modules, "app.logger", fake_logger)

    fake_conversions = types.ModuleType("app.utils.formatting.conversions")

    def as_int(value):
        try:
            return int(value)
        except TypeError:
            return None
        except ValueError:
            return None

    fake_conversions.as_int = as_int
    monkeypatch.setitem(sys.modules, "app.utils.formatting.conversions", fake_conversions)

    service_model = _load_module(
        "app.db.models.services",
        PROJECT_ROOT / "app/db/models/services.py",
    )
    crud_module_name = "service_search_crud_under_test"
    crud = _load_module(
        crud_module_name,
        PROJECT_ROOT / "app/db/crud/services.py",
    )

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    crud.Session = session_factory

    async with engine.begin() as connection:
        await connection.run_sync(base.metadata.create_all)

    yield crud, service_model.Service, session_factory

    await engine.dispose()
    sys.modules.pop(crud_module_name, None)


async def _insert_services(session_factory, service_model, rows: list[dict]) -> None:
    async with session_factory() as session:
        session.add_all(service_model(**row) for row in rows)
        await session.commit()


def test_search_query_normalizes_at_sign_whitespace_and_persian_digits(search_helpers) -> None:
    assert search_helpers.normalize_service_search_query("  @TeSt_۱۲٣  ") == "TeSt_123"
    assert search_helpers.normalize_service_search_query("  ١٢ ٣٤  ") == "1234"


def test_search_query_rejects_empty_and_oversized_values(search_helpers) -> None:
    query, error = search_helpers.validate_service_search_query("  @  ")
    assert query is None
    assert "خالی" in error

    query, error = search_helpers.validate_service_search_query("a" * 129)
    assert query is None
    assert "128" in error


@pytest.mark.asyncio
async def test_contains_search_is_case_insensitive_ranked_and_owner_scoped(service_db) -> None:
    crud, service_model, session_factory = service_db
    await _insert_services(
        session_factory,
        service_model,
        [
            {"code": 2001, "username": "prefix-alpha-tail", "id": 111, "in_panel": 1, "createtime": 300},
            {"code": 2002, "username": "ALPHA", "id": 111, "in_panel": 1, "createtime": 100},
            {"code": 2003, "username": "private-alpha", "id": 222, "in_panel": 1, "createtime": 400},
        ],
    )

    services, total = await crud.get_user_services_paginated(
        user_id=111,
        search="alpha",
        contains=True,
    )

    assert total == 2
    assert [service.code for service in services] == [2002, 2001]
    assert all(service.id == 111 for service in services)


@pytest.mark.asyncio
async def test_search_treats_sql_wildcards_as_literal_text(service_db) -> None:
    crud, service_model, session_factory = service_db
    await _insert_services(
        session_factory,
        service_model,
        [
            {"code": 3001, "username": "name_one", "id": 111, "createtime": 3},
            {"code": 3002, "username": "nameXone", "id": 111, "createtime": 2},
            {"code": 3003, "username": "discount%user", "id": 111, "createtime": 1},
        ],
    )

    underscore, underscore_total = await crud.get_user_services_paginated(
        user_id=111,
        search="_",
        contains=True,
    )
    percent, percent_total = await crud.get_user_services_paginated(
        user_id=111,
        search="%",
        contains=True,
    )

    assert underscore_total == 1
    assert [service.code for service in underscore] == [3001]
    assert percent_total == 1
    assert [service.code for service in percent] == [3003]


@pytest.mark.asyncio
async def test_numeric_search_uses_exact_service_code_not_code_prefix(service_db) -> None:
    crud, service_model, session_factory = service_db
    await _insert_services(
        session_factory,
        service_model,
        [
            {"code": 1234, "username": "first-user", "id": 111, "createtime": 1},
            {"code": 12345, "username": "second-user", "id": 111, "createtime": 2},
        ],
    )

    services, total = await crud.get_user_services_paginated(
        user_id=111,
        search="1234",
        contains=True,
    )

    assert total == 1
    assert [service.code for service in services] == [1234]


@pytest.mark.asyncio
async def test_service_list_is_paginated_in_the_database(service_db) -> None:
    crud, service_model, session_factory = service_db
    await _insert_services(
        session_factory,
        service_model,
        [
            {
                "code": 4000 + number,
                "username": f"user-{number}",
                "id": 111,
                "createtime": number,
            }
            for number in range(15)
        ],
    )

    services, total = await crud.get_user_services_paginated(user_id=111, page=2, limit=10)

    assert total == 15
    assert len(services) == 5
    assert [service.createtime for service in services] == [4, 3, 2, 1, 0]
