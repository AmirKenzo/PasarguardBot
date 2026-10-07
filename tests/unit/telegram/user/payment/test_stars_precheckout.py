"""Telegram Stars pre-checkout: only a fresh pending invoice may be paid."""

from __future__ import annotations

from types import SimpleNamespace

from app.telegram.user.payment.stars_precheckout import STARS_INVOICE_TTL_SECONDS, stars_precheckout_ok

NOW = 1_700_000_000


def _tx(status: str, age_seconds: int) -> SimpleNamespace:
    return SimpleNamespace(status=status, created_at=NOW - age_seconds)


def test_recent_pending_invoice_is_accepted():
    assert stars_precheckout_ok(_tx("pending", 10), now=NOW) is True


def test_pending_invoice_is_rejected_exactly_at_ttl():
    assert stars_precheckout_ok(_tx("pending", STARS_INVOICE_TTL_SECONDS), now=NOW) is False


def test_pending_invoice_is_rejected_after_ttl():
    assert stars_precheckout_ok(_tx("pending", STARS_INVOICE_TTL_SECONDS + 1), now=NOW) is False


def test_expired_invoice_is_rejected():
    assert stars_precheckout_ok(_tx("expired", 10), now=NOW) is False


def test_already_approved_invoice_is_rejected():
    assert stars_precheckout_ok(_tx("approved", 10), now=NOW) is False


def test_missing_invoice_is_rejected():
    assert stars_precheckout_ok(None, now=NOW) is False
