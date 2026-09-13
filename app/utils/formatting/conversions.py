"""Shared unit and time conversions used across handlers, cron, and webhooks."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


def as_int(value: int | str | None) -> int | None:
    """Coerce callback/step string IDs to int (PostgreSQL strict typing)."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    try:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            return int(stripped)
        return int(value)
    except TypeError, ValueError:
        return None


def gigabytes_to_bytes(gb: float) -> int:
    return int(float(gb) * (1024**3))


def days_to_microseconds(days: int) -> int:
    return int(days) * 86400 * 10**6


def day_to_milliseconds(days: int) -> int:
    expiry_time = datetime.now() + timedelta(days=int(days))
    return int(expiry_time.timestamp() * 1000)


def day_to_seconds(days: int) -> int:
    return int(days) * 86400


def day_to_timestamp(days: int) -> int:
    """Unix timestamp for now + days using naive local datetime (legacy handler behavior)."""
    expiry_time = datetime.now() + timedelta(days=int(days))
    return int(expiry_time.timestamp())


def day_to_timestamp_utc(days: int) -> int:
    """Unix timestamp for now + days in UTC."""
    expiry_time = datetime.now(UTC) + timedelta(days=int(days))
    return int(expiry_time.timestamp())


def to_unix_timestamp(value: object) -> int | None:
    """Best-effort conversion of a datetime/int/float value to a unix timestamp."""

    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    try:
        return int(value.timestamp())  # type: ignore[union-attr]
    except AttributeError:
        return None


def convert_storage(
    volume: float,
    plan_type: str | None = None,
    data_limit_reset_strategy: str | None = None,
    for_button: bool = False,
) -> str:
    if isinstance(volume, float) and volume.is_integer():
        volume_int = int(volume)
    elif isinstance(volume, int):
        volume_int = volume
    else:
        volume_int = volume

    if volume_int < 1:
        volume_text = f"{volume_int * 1000:.0f} مگ"
    elif volume_int < 1000:
        volume_text = f"{volume_int} گیگ"
    else:
        volume_text = f"{volume_int / 1000:.2f} ترا"

    if plan_type == "unlimited_volume":
        if for_button:
            return "نامحدود"
        return f"{volume_text} (مصرف منصفانه)"

    if data_limit_reset_strategy and data_limit_reset_strategy != "no_reset":
        reset_map = {"day": "روزانه", "week": "هفتگی", "month": "ماهانه", "year": "سالانه"}
        prefix = reset_map.get(data_limit_reset_strategy, "نامحدود")
        return f"{prefix} {volume_text} (ریست می‌شود)"

    if plan_type and plan_type in ("fair_usage", "fair"):
        return f"{volume_text} (مصرف منصفانه)"

    return volume_text


def convert_storage_float(
    volume: float,
    plan_type: str | None = None,
    data_limit_reset_strategy: str | None = None,
    for_button: bool = False,
) -> str:
    """Float-based storage label (legacy utils.py / webapp behavior)."""
    vol = float(volume)
    if vol < 1:
        volume_text = f"{vol * 1000:.0f} مگ"
    elif vol < 1000:
        volume_text = f"{int(vol)} گیگ"
    else:
        volume_text = f"{vol / 1000:.2f} ترا"
    if plan_type == "unlimited_volume":
        return "نامحدود" if for_button else f"{volume_text} (مصرف منصفانه)"
    if data_limit_reset_strategy and data_limit_reset_strategy != "no_reset":
        reset_map = {"day": "روزانه", "week": "هفتگی", "month": "ماهانه", "year": "سالانه"}
        prefix = reset_map.get(data_limit_reset_strategy, "نامحدود")
        return f"{prefix} {volume_text} (ریست می‌شود)"
    if plan_type and plan_type in ("fair_usage", "fair"):
        return f"{volume_text} (مصرف منصفانه)"
    return volume_text
