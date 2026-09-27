from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_mod = _load("crypto_amounts_under_test", PROJECT_ROOT / "app/services/pricing/crypto_amounts.py")
calculate_trx_amount_with_tax = _mod.calculate_trx_amount_with_tax


def test_retries_dust_when_amount_reserved():
    with patch.object(_mod.random, "uniform", return_value=0):
        first = asyncio.run(calculate_trx_amount_with_tax(10_000, 100_000))
        second = asyncio.run(calculate_trx_amount_with_tax(10_000, 100_000, reserved_amounts={first}))
    assert second != first
    assert second == round(first + 0.000001, 6)


def test_raises_when_unique_amount_exhausted():
    with patch.object(_mod.random, "uniform", return_value=0):
        first = asyncio.run(calculate_trx_amount_with_tax(10_000, 100_000))
        reserved = {round(first + i * 0.000001, 6) for i in range(21)}
        with pytest.raises(ValueError, match="could not allocate unique crypto amount"):
            asyncio.run(calculate_trx_amount_with_tax(10_000, 100_000, reserved_amounts=reserved))
