from __future__ import annotations

import random

_DUST_ATTEMPTS = 20
_STEP = 0.000001


def _norm6(value) -> str:
    return f"{round(float(value), 6):.6f}"


def _amount_with_tax(price, amount_in_toman, tax_percentage, reserved_amounts):
    reserved = {_norm6(x) for x in (reserved_amounts or [])}
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
