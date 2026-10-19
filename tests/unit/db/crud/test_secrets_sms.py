from __future__ import annotations

from typing import Any

import pytest

from app.db.crud import secrets as secrets_mod
from app.utils.security.secrets_cache import (
    SECRET_CRYPTO_KEY,
    SECRET_SMS_WEBHOOK,
    SECRET_WEBHOOK,
    _cache,
    get_sms_webhook_secret,
)


class _Query:
    def __init__(self, rows: list[Any]) -> None:
        self.rows = rows

    def where(self, *_: Any) -> _Query:
        return self

    def scalars(self) -> _Query:
        return self

    def all(self) -> list[Any]:
        return self.rows

    def first(self) -> Any:
        return self.rows[0] if self.rows else None


class _Session:
    def __init__(self, rows: dict[str, Any]) -> None:
        self.rows = rows
        self.commits = 0

    async def __aenter__(self) -> _Session:
        return self

    async def __aexit__(self, *_: Any) -> None:
        return None

    async def execute(self, query: _Query) -> _Query:
        return query

    def add(self, row: Any) -> None:
        self.rows[row.name] = row

    async def commit(self) -> None:
        self.commits += 1


class _Column:
    def in_(self, *_: Any) -> None:
        return None

    def __eq__(self, _: object) -> bool:
        return True

    __hash__ = object.__hash__


class _Secret:
    name: Any = _Column()

    def __init__(self, name: str, value: str) -> None:
        self.name = name
        self.value = value


def _use(monkeypatch: pytest.MonkeyPatch, rows: dict[str, Any]) -> _Session:
    session = _Session(rows)
    monkeypatch.setattr(secrets_mod, "Session", lambda: session)
    monkeypatch.setattr(secrets_mod, "Secret", _Secret)
    monkeypatch.setattr(secrets_mod, "select", lambda *_: _Query(list(session.rows.values())))
    return session


@pytest.fixture(autouse=True)
def _clean_sms_cache():
    _cache.pop(SECRET_SMS_WEBHOOK, None)
    yield
    _cache.pop(SECRET_SMS_WEBHOOK, None)


def _core_rows() -> dict[str, Any]:
    return {
        SECRET_CRYPTO_KEY: _Secret(SECRET_CRYPTO_KEY, "crypto"),
        SECRET_WEBHOOK: _Secret(SECRET_WEBHOOK, "hook"),
    }


async def test_missing_sms_row_gets_random_key(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _use(monkeypatch, _core_rows())

    await secrets_mod.SecretsCRUD().ensure_secrets()

    value = session.rows[SECRET_SMS_WEBHOOK].value
    assert len(value) == 64
    assert get_sms_webhook_secret() == value
    assert session.commits == 1


async def test_existing_sms_row_is_loaded(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = _core_rows()
    rows[SECRET_SMS_WEBHOOK] = _Secret(SECRET_SMS_WEBHOOK, "db-key-0123456789abc")
    _use(monkeypatch, rows)

    await secrets_mod.SecretsCRUD().ensure_secrets()

    assert get_sms_webhook_secret() == "db-key-0123456789abc"
    assert rows[SECRET_SMS_WEBHOOK].value == "db-key-0123456789abc"


async def test_rotate_replaces_db_row_and_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    row = _Secret(SECRET_SMS_WEBHOOK, "old-key-0123456789abc")
    session = _use(monkeypatch, {SECRET_SMS_WEBHOOK: row})
    _cache[SECRET_SMS_WEBHOOK] = row.value

    new_value = await secrets_mod.SecretsCRUD().rotate(SECRET_SMS_WEBHOOK)

    assert new_value != "old-key-0123456789abc"
    assert len(new_value) == 64
    assert row.value == new_value
    assert get_sms_webhook_secret() == new_value
    assert session.commits == 1


async def test_rotate_unknown_secret_is_refused() -> None:
    with pytest.raises(ValueError):
        await secrets_mod.SecretsCRUD().rotate("nope")
