from __future__ import annotations

import random
from collections.abc import Awaitable, Callable
from typing import Any

_DUST_ATTEMPTS = 20
_STEP = 0.000001
# Same tax the calculate_*_amount_with_tax helpers apply by default.
_DEFAULT_TAX_PERCENTAGE = 9


def _norm6(value) -> str:
    return f"{round(float(value), 6):.6f}"


def _reserved_with_neighbors(reserved_amounts) -> set[str]:
    """Reserved amounts plus one step either side: the jobs match within one step."""
    reserved: set[str] = set()
    for value in reserved_amounts or []:
        try:
            base = float(value)
        except TypeError, ValueError:
            continue
        for offset in (-_STEP, 0.0, _STEP):
            reserved.add(_norm6(base + offset))
    return reserved


def _amount_with_tax(price, amount_in_toman, tax_percentage, reserved_amounts):
    reserved = _reserved_with_neighbors(reserved_amounts)
    last = 0.0
    for _ in range(_DUST_ATTEMPTS):
        raw = amount_in_toman / price
        last = round(raw + raw * (tax_percentage / 100) + random.uniform(0, 0.0001), 6)
        if _norm6(last) not in reserved:
            return last
    for step in range(1, _DUST_ATTEMPTS + 1):
        bumped = round(last + step * _STEP, 6)
        if _norm6(bumped) not in reserved:
            return bumped
    raise ValueError("could not allocate unique crypto amount")


async def calculate_trx_amount_with_tax(price_per_trx, amount_in_toman, tax_percentage=9, reserved_amounts=None):
    return _amount_with_tax(price_per_trx, amount_in_toman, tax_percentage, reserved_amounts)


async def calculate_usdt_amount_with_tax(price_per_usdt, amount_in_toman, tax_percentage=9, reserved_amounts=None):
    return _amount_with_tax(price_per_usdt, amount_in_toman, tax_percentage, reserved_amounts)


async def calculate_ton_amount_with_tax(price_per_ton, amount_in_toman, tax_percentage=9, reserved_amounts=None):
    return _amount_with_tax(price_per_ton, amount_in_toman, tax_percentage, reserved_amounts)


async def calculate_pol_amount_with_tax(price_per_pol, amount_in_toman, tax_percentage=9, reserved_amounts=None):
    return _amount_with_tax(price_per_pol, amount_in_toman, tax_percentage, reserved_amounts)


# Settings attribute holding the toman price of each invoice currency.
_PRICE_SETTING = {
    "trx": "arz_trx",
    "usdt": "arz_usd",
    "usdt-ton": "arz_usd",
    "usdt-bep20": "arz_usd",
    "ton": "arz_ton",
    "pol": "arz_pol",
}


def crypto_amount_picker(currency: str, settings: Any, amount_in_toman: int) -> Callable[[set[str]], Awaitable[float]]:
    """Amount picker for ``add_order_with_unique_amount``: avoids the reserved amounts it is given."""
    attr = _PRICE_SETTING.get((currency or "").lower())
    if attr is None:
        raise ValueError(f"unsupported crypto currency: {currency}")
    price = int(getattr(settings, attr, 0) or 0)
    if price <= 0:
        raise ValueError(f"price for {currency} is not configured")

    async def pick(reserved: set[str]) -> float:
        return _amount_with_tax(price, amount_in_toman, _DEFAULT_TAX_PERCENTAGE, reserved)

    return pick
