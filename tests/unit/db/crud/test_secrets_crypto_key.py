"""ensure_secrets must never silently replace crypto_key while encrypted data exists."""

from __future__ import annotations

from typing import Any

import pytest

from app.db.crud import secrets as secrets_mod
from app.utils.security.secrets_cache import SECRET_CRYPTO_KEY, SECRET_WEBHOOK, _cache
from tests.unit.db.crud.test_secrets_sms import _Secret, _use


@pytest.fixture(autouse=True)
def _clean_cache():
    saved = dict(_cache)
    yield
    _cache.clear()
    _cache.update(saved)


def _rows_without_crypto(empty_row: bool) -> dict[str, Any]:
    rows: dict[str, Any] = {SECRET_WEBHOOK: _Secret(SECRET_WEBHOOK, "hook")}
    if empty_row:
        rows[SECRET_CRYPTO_KEY] = _Secret(SECRET_CRYPTO_KEY, "  ")
    return rows


def _encrypted_data(monkeypatch: pytest.MonkeyPatch, exists: bool) -> None:
    async def _fake(_session: Any) -> bool:
        return exists

    monkeypatch.setattr(secrets_mod, "_has_encrypted_data", _fake)


@pytest.mark.parametrize("empty_row", [False, True])
async def test_refuses_new_crypto_key_when_encrypted_data_exists(
    monkeypatch: pytest.MonkeyPatch, empty_row: bool
) -> None:
    session = _use(monkeypatch, _rows_without_crypto(empty_row))
    _encrypted_data(monkeypatch, exists=True)

    with pytest.raises(RuntimeError, match="crypto_key"):
        await secrets_mod.SecretsCRUD().ensure_secrets()

    assert session.commits == 0
    if empty_row:
        assert session.rows[SECRET_CRYPTO_KEY].value == "  "
    else:
        assert SECRET_CRYPTO_KEY not in session.rows


async def test_fresh_install_generates_crypto_key(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _use(monkeypatch, _rows_without_crypto(empty_row=False))
    _encrypted_data(monkeypatch, exists=False)

    await secrets_mod.SecretsCRUD().ensure_secrets()

    assert len(session.rows[SECRET_CRYPTO_KEY].value) == 64
    assert session.commits == 1
