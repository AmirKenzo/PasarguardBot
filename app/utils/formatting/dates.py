from __future__ import annotations

from datetime import UTC, datetime

import jdatetime
import pytz

IRAN_TZ = pytz.timezone("Asia/Tehran")


def timestamp_to_persian_expiry(value: int | float | str | datetime) -> str:
    """
    Convert a Unix timestamp, datetime, or ISO-8601 string to a Jalali expiry label.
    """
    if isinstance(value, datetime):
        expiry_dt = value.astimezone(UTC)
    elif isinstance(value, (int, float)):
        expiry_dt = datetime.fromtimestamp(value, tz=UTC)
    elif isinstance(value, str):
        try:
            expiry_dt = datetime.fromisoformat(value).astimezone(UTC)
        except ValueError:
            expiry_dt = datetime.fromtimestamp(int(value), tz=UTC)
    else:
        raise TypeError("value must be datetime, timestamp, or ISO-8601 string")

    now = datetime.now(UTC)
    remaining = expiry_dt - now

    expiry_jalali = jdatetime.datetime.fromgregorian(datetime=expiry_dt)
    expiry_jalali_str = expiry_jalali.strftime("%Y/%m/%d")

    if remaining.total_seconds() <= 0:
        return f"{expiry_jalali_str} (زمان اکانت شما به پایان رسیده)"

    days = remaining.days
    hours, rem = divmod(remaining.seconds, 3600)
    minutes, _ = divmod(rem, 60)

    parts: list[str] = []
    if days:
        parts.append(f"{days} روز")
    if hours:
        parts.append(f"{hours} ساعت")
    if minutes:
        parts.append(f"{minutes} دقیقه")

    time_str = " و ".join(parts) + " دیگر" if parts else "کمتر از یک دقیقه دیگر"
    return f"{expiry_jalali_str} ({time_str})"


def Time_Date(value=None):
    if value is None:
        dt = datetime.now(tz=UTC)
    elif isinstance(value, (int, float)):
        dt = datetime.fromtimestamp(value, tz=UTC)
    elif isinstance(value, datetime):
        dt = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    elif isinstance(value, str):
        try:
            iso = value.replace("Z", "+00:00") if value.endswith("Z") else value
            dt_parsed = datetime.fromisoformat(iso)
            dt = dt_parsed.replace(tzinfo=UTC) if dt_parsed.tzinfo is None else dt_parsed.astimezone(UTC)
        except Exception:
            return {"error": "Invalid datetime string format"}
    else:
        return {"error": "Unsupported input type"}

    iran_time = dt.astimezone(IRAN_TZ)
    miladi = iran_time.strftime("%Y/%m/%d")
    miladi_full = iran_time.strftime("%Y/%m/%d %H:%M:%S")

    jalali_date = jdatetime.datetime.fromgregorian(datetime=iran_time)
    jalali = jalali_date.strftime("%Y/%m/%d")
    jalali_full = jalali_date.strftime("%Y/%m/%d %H:%M:%S")

    now_stamp = int(datetime.now(tz=UTC).timestamp())
    value_stamp = int(dt.timestamp())
    diff = value_stamp - now_stamp
    days = abs(diff) // 86400
    hours = (abs(diff) % 86400) // 3600
    minutes = (abs(diff) % 3600) // 60

    if diff > 0:
        remaining = f"{days} روز، {hours} ساعت و {minutes} دقیقه دیگر"
    elif diff < 0:
        remaining = "زمان به اتمام رسیده"
    else:
        remaining = "همین لحظه"

    return {
        "m": miladi,
        "mf": miladi_full,
        "j": jalali,
        "jf": jalali_full,
        "stamp": value_stamp,
        "remaining_days": remaining,
    }


def relative_time(timestamp):
    """Convert timestamp/datetime/ISO text to a Persian relative time label."""
    if timestamp is None:
        return "نامشخص"

    if isinstance(timestamp, (int, float)):
        dt = datetime.fromtimestamp(timestamp, tz=UTC)
    elif isinstance(timestamp, datetime):
        dt = timestamp.replace(tzinfo=UTC) if timestamp.tzinfo is None else timestamp.astimezone(UTC)
    elif isinstance(timestamp, str):
        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            dt = dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)
        except Exception:
            return "نامشخص"
    else:
        return "نامشخص"

    now = datetime.now(tz=UTC)
    diff = (now - dt).total_seconds()

    if diff < 60:
        return "همین الان"

    minutes = int(diff // 60)
    if minutes < 60:
        return f"{minutes} دقیقه پیش"

    hours = int(diff // 3600)
    if hours < 24:
        return f"{hours} ساعت پیش"

    days = int(diff // 86400)
    if days < 30:
        return f"{days} روز پیش"

    iran_time = dt.astimezone(IRAN_TZ)
    return iran_time.strftime("%Y/%m/%d %H:%M")
