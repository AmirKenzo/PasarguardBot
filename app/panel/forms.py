"""Small parsers shared by the panel forms."""

from __future__ import annotations

import re

# Shapes the bot also accepts when an icon is sent in Telegram.
_ICON_PATTERNS = (r"^(\d+)$", r"emoji/(\d+)", r"tg://emoji\?id=(\d+)")

BUTTON_STYLES: tuple[tuple[str, str], ...] = (
    ("", "پیش‌فرض"),
    ("primary", "آبی"),
    ("success", "سبز"),
    ("danger", "قرمز"),
)


def parse_icon(raw: str) -> int | None:
    """Read a custom emoji document id from digits, ``emoji/ID`` or ``tg://emoji?id=ID``.

    Returns ``None`` for empty input and raises ``ValueError`` for anything else.
    """
    text = (raw or "").strip()
    if not text:
        return None
    for pattern in _ICON_PATTERNS:
        match = re.search(pattern, text)
        if match:
            return int(match.group(1))
    raise ValueError(text)


def parse_style(raw: str) -> str | None:
    style = (raw or "").strip()
    if style not in {value for value, _ in BUTTON_STYLES}:
        return None
    return style or None


def parse_int(raw, default: int = 0, *, minimum: int | None = None, maximum: int | None = None) -> int:
    try:
        value = int(float(str(raw).replace(",", "").strip()))
    except TypeError, ValueError:
        value = default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value
