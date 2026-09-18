from __future__ import annotations

import random


async def calculate_trx_amount_with_tax(price_per_trx, amount_in_toman, tax_percentage=9):
    trx_amount = amount_in_toman / price_per_trx
    tax_amount = trx_amount * (tax_percentage / 100)
    trx_amount_with_tax = trx_amount + tax_amount
    trx_amount_with_tax += random.uniform(0, 0.0001)
    return round(trx_amount_with_tax, 6)


async def calculate_usdt_amount_with_tax(price_per_usdt, amount_in_toman, tax_percentage=9):
    usdt_amount = amount_in_toman / price_per_usdt
    tax_amount = usdt_amount * (tax_percentage / 100)
    usdt_amount_with_tax = usdt_amount + tax_amount
    usdt_amount_with_tax += random.uniform(0, 0.0001)
    return round(usdt_amount_with_tax, 6)


async def calculate_ton_amount_with_tax(price_per_ton, amount_in_toman, tax_percentage=9):
    ton_amount = amount_in_toman / price_per_ton
    tax_amount = ton_amount * (tax_percentage / 100)
    ton_amount_with_tax = ton_amount + tax_amount
    ton_amount_with_tax += random.uniform(0, 0.0001)
    return round(ton_amount_with_tax, 6)


async def calculate_pol_amount_with_tax(price_per_pol, amount_in_toman, tax_percentage=9):
    pol_amount = amount_in_toman / price_per_pol
    tax_amount = pol_amount * (tax_percentage / 100)
    pol_amount_with_tax = pol_amount + tax_amount
    pol_amount_with_tax += random.uniform(0, 0.0001)
    return round(pol_amount_with_tax, 6)
