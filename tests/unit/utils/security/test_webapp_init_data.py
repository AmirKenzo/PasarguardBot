"""Telegram initData must carry a valid signature and a fresh, signed auth_date."""

from __future__ import annotations

import hashlib
import hmac
from urllib.parse import parse_qsl, urlencode

from app.utils.security.webapp_auth import WEBAPP_INIT_DATA_MAX_AGE_SECONDS, validate_webapp_data
from config import BOT_TOKEN

NOW = 1_800_000_000


def _signed(fields: dict[str, str]) -> dict[str, str]:
    """Sign fields the way Telegram does and return the parsed payload."""
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    digest = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return dict(parse_qsl(urlencode({**fields, "hash": digest})))


def _init_data(auth_date: int | None) -> dict[str, str]:
    fields = {"user": '{"id": 42}', "query_id": "AAA"}
    if auth_date is not None:
        fields["auth_date"] = str(auth_date)
    return _signed(fields)


def test_fresh_init_data_is_accepted():
    assert validate_webapp_data(_init_data(NOW - 60), now=NOW) == (True, None)


def test_init_data_at_max_age_is_accepted():
    ok, _ = validate_webapp_data(_init_data(NOW - WEBAPP_INIT_DATA_MAX_AGE_SECONDS), now=NOW)
    assert ok is True


def test_init_data_older_than_max_age_is_rejected():
    ok, _ = validate_webapp_data(_init_data(NOW - WEBAPP_INIT_DATA_MAX_AGE_SECONDS - 1), now=NOW)
    assert ok is False


def test_init_data_without_auth_date_is_rejected():
    ok, _ = validate_webapp_data(_init_data(None), now=NOW)
    assert ok is False


def test_init_data_from_the_future_is_rejected():
    ok, _ = validate_webapp_data(_init_data(NOW + 3600), now=NOW)
    assert ok is False


def test_tampered_auth_date_breaks_signature():
    payload = _init_data(NOW - 10 * WEBAPP_INIT_DATA_MAX_AGE_SECONDS)
    payload["auth_date"] = str(NOW)
    ok, _ = validate_webapp_data(payload, now=NOW)
    assert ok is False


def test_custom_max_age_is_enforced():
    ok, _ = validate_webapp_data(_init_data(NOW - 600), max_age_seconds=300, now=NOW)
    assert ok is False
