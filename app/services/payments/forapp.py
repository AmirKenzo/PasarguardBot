"""ForApp auto-verify core: unique-amount offset matching for card-to-card deposits.

Port of the Node.js `lib/forapp.ts` blueprint to this Python bot. The matching
strategy is: every pending manual top-up reserves a unique payable amount
``base + offset (1..999 toman)``. ForApp (Android SMS app) POSTs bank deposit
SMS to our webhook; we normalize rial->toman and match by payable amount.
"""

from __future__ import annotations

import hmac
import os
import random
from collections.abc import Iterable

FORAPP_OFFSET_MIN = 1
FORAPP_OFFSET_MAX = 999
_RESERVE_TRIES = 60


def get_forapp_api_keys(env: dict | None = None) -> list[str]:
    if env is None:
        raw = os.getenv("FORAPP_API_KEYS", "") or os.getenv("FORAPP_API_KEY", "") or os.getenv("FORAPP_SECRET", "")
    else:
        raw = env.get("FORAPP_API_KEYS", "") or env.get("FORAPP_API_KEY", "") or env.get("FORAPP_SECRET", "") or ""
    return [k.strip() for k in str(raw).split(",") if k and k.strip()]


def is_valid_forapp_key(provided: str | None, allowed_keys: list[str]) -> bool:
    if not provided or not allowed_keys:
        return False
    p = provided.strip()
    if not p:
        return False
    return any(hmac.compare_digest(p, k) for k in allowed_keys if k)


def normalize_to_toman(raw: float | int, unit: str | None) -> int | None:
    """Convert a raw bank SMS amount to toman. Most Iranian bank SMS are in rial."""
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if value != value or value in (float("inf"), float("-inf")) or value <= 0:  # NaN/inf guard
        return None
    u = (unit or "").strip().lower()
    if u in ("toman", "tmn", "تومان"):
        return round(value)
    if u in ("rial", "irr", "ریال", ""):
        return round(value / 10)
    return round(value)


def forapp_candidates(raw: float | int, unit: str | None) -> list[int]:
    """Possible toman values when the bank/SMS unit is ambiguous."""
    out: list[int] = []
    primary = normalize_to_toman(raw, unit)
    if primary and primary > 0:
        out.append(primary)
    rounded = round(float(raw))
    if rounded > 0 and rounded not in out:
        out.append(rounded)
    try:
        if float(raw) / 10 == int(float(raw) // 10) or float(raw) % 10 == 0:
            divided = round(float(raw) / 10)
            if divided > 0 and divided not in out:
                out.append(divided)
    except (TypeError, ValueError):
        pass
    return out


def reserve_payable_amount(
    base_amount: int,
    reserved_payables: Iterable[int] | set[int],
    min_offset: int = FORAPP_OFFSET_MIN,
    max_offset: int = FORAPP_OFFSET_MAX,
    random_fn=None,
) -> tuple[int, int] | None:
    """Pick a unique ``(payable, offset)`` not present in ``reserved_payables``.

    Returns None when all 999 slots for this base are taken.
    """
    base = int(base_amount)
    reserved = reserved_payables if isinstance(reserved_payables, set) else {int(x) for x in reserved_payables}
    rand = random_fn or random.random
    for _ in range(_RESERVE_TRIES):
        offset = min_offset + int(rand() * (max_offset - min_offset + 1))
        payable = base + offset
        if payable not in reserved:
            return payable, offset
    for offset in range(min_offset, max_offset + 1):
        payable = base + offset
        if payable not in reserved:
            return payable, offset
    return None


def coerce_raw_amount(v) -> float | int | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return v if v > 0 else None
    if isinstance(v, str):
        try:
            n = float(v.replace(",", "").strip())
        except ValueError:
            return None
        return n if n > 0 else None
    return None
