"""Unique crypto amounts: a reserved amount gets a dust offset, and allocation gives up when exhausted."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from app.services.pricing import crypto_amounts
from app.services.pricing.crypto_amounts import calculate_trx_amount_with_tax


def test_reserved_amount_gets_next_dust_offset():
    with patch.object(crypto_amounts.random, "uniform", return_value=0):
        first = asyncio.run(calculate_trx_amount_with_tax(10_000, 100_000))
        second = asyncio.run(calculate_trx_amount_with_tax(10_000, 100_000, reserved_amounts={first}))

    assert second != first
    assert second == round(first + 0.000001, 6)


def test_raises_when_every_dust_offset_is_reserved():
    with patch.object(crypto_amounts.random, "uniform", return_value=0):
        first = asyncio.run(calculate_trx_amount_with_tax(10_000, 100_000))
        reserved = {round(first + i * 0.000001, 6) for i in range(21)}

        with pytest.raises(ValueError, match="could not allocate unique crypto amount"):
            asyncio.run(calculate_trx_amount_with_tax(10_000, 100_000, reserved_amounts=reserved))
