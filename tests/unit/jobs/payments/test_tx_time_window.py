"""On-chain tx time window for crypto invoices, including explorers that omit timestamps."""

from __future__ import annotations

from types import SimpleNamespace

from app.jobs.payments import crypto_common
from app.jobs.payments.crypto_common import INVOICE_TTL_SECONDS, TX_TIME_TOLERANCE_SECONDS, tx_time_in_window

CREATED = 1_700_000_000


def _payment() -> SimpleNamespace:
    return SimpleNamespace(createtime=CREATED)


def test_known_time_must_fall_inside_ttl_plus_tolerance():
    payment = _payment()
    assert not tx_time_in_window(payment, CREATED - 1)
    assert tx_time_in_window(payment, CREATED)
    assert tx_time_in_window(payment, CREATED + INVOICE_TTL_SECONDS + TX_TIME_TOLERANCE_SECONDS)
    assert not tx_time_in_window(payment, CREATED + INVOICE_TTL_SECONDS + TX_TIME_TOLERANCE_SECONDS + 1)


def test_unknown_time_rejected_by_default(monkeypatch):
    monkeypatch.setattr(crypto_common.time, "time", lambda: CREATED + 60)
    assert not tx_time_in_window(_payment(), None)
    assert not tx_time_in_window(_payment(), 0)


def test_unknown_time_allowed_only_inside_ttl(monkeypatch):
    monkeypatch.setattr(crypto_common.time, "time", lambda: CREATED + INVOICE_TTL_SECONDS)
    assert tx_time_in_window(_payment(), None, allow_unknown=True)
    monkeypatch.setattr(crypto_common.time, "time", lambda: CREATED + INVOICE_TTL_SECONDS + 1)
    assert not tx_time_in_window(_payment(), None, allow_unknown=True)
