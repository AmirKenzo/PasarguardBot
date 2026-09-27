from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_mod = _load("stars_precheckout_under_test", PROJECT_ROOT / "app/telegram/user/payment/stars_precheckout.py")
stars_precheckout_ok = _mod.stars_precheckout_ok
STARS_INVOICE_TTL_SECONDS = _mod.STARS_INVOICE_TTL_SECONDS


def test_pending_recent_ok():
    now = 1_700_000_000
    tx = SimpleNamespace(status="pending", created_at=now - 10)
    assert stars_precheckout_ok(tx, now=now) is True


def test_pending_ttl_elapsed():
    now = 1_700_000_000
    tx = SimpleNamespace(status="pending", created_at=now - STARS_INVOICE_TTL_SECONDS)
    assert stars_precheckout_ok(tx, now=now) is False


def test_pending_past_ttl():
    now = 1_700_000_000
    tx = SimpleNamespace(status="pending", created_at=now - STARS_INVOICE_TTL_SECONDS - 1)
    assert stars_precheckout_ok(tx, now=now) is False


def test_expired_status_rejected():
    now = 1_700_000_000
    tx = SimpleNamespace(status="expired", created_at=now - 10)
    assert stars_precheckout_ok(tx, now=now) is False


def test_approved_status_rejected():
    now = 1_700_000_000
    tx = SimpleNamespace(status="approved", created_at=now - 10)
    assert stars_precheckout_ok(tx, now=now) is False


def test_missing_tx_rejected():
    assert stars_precheckout_ok(None, now=1_700_000_000) is False
