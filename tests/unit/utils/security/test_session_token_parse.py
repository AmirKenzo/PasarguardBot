"""Session tokens are HMAC-only; anything else is refused without any key derivation."""

from __future__ import annotations

import asyncio

import pytest

from app.utils.security import webapp_auth


@pytest.fixture(autouse=True)
def signing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(webapp_auth, "_session_signing_key", lambda: b"test-key")


def test_hmac_token_round_trips() -> None:
    token = webapp_auth.create_session_token(42, session_version=3)
    ok, err, payload = asyncio.run(webapp_auth.parse_session_token_async(token))
    assert ok is True and err is None
    assert payload["uid"] == 42 and payload["ver"] == 3


@pytest.mark.parametrize("token", ["aaaa", "bm90LWEtdG9rZW4=" * 8, "1.2.3", ""])
def test_non_hmac_token_is_rejected_without_decrypting(token: str, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args, **kwargs):
        raise AssertionError("crypto key must not be touched for a non-HMAC token")

    monkeypatch.setattr(webapp_auth, "get_crypto_key", boom)
    ok, _err, payload = asyncio.run(webapp_auth.parse_session_token_async(token))
    assert ok is False and payload is None


def test_tampered_signature_is_rejected() -> None:
    token = webapp_auth.create_session_token(42)
    forged = token[:-1] + ("0" if token[-1] != "0" else "1")
    assert webapp_auth.parse_session_token(forged)[0] is False
