"""The "glassy" button label.

Telegram buttons have no translucency, so the look is faked with brackets
around the label. That makes it a property of the text rather than of
Telegram's button style, which is why it lives here: both the code that draws
a keyboard and the code that matches an incoming press against a button label
need the same answer, and they sit on opposite sides of the app.
"""

from __future__ import annotations

GLASS_STYLE = "glass"

GLASS_LEFT = "「"
GLASS_RIGHT = "」"
GLASS_ICON = ""


def glass_text(label: str, *, icon: str = GLASS_ICON) -> str:
    """Wrap a label in the glassy brackets."""
    label = (label or "").strip()
    if not label:
        return f"{GLASS_LEFT}{GLASS_ICON}{GLASS_RIGHT}"
    return f"{GLASS_LEFT}{icon} {label}{GLASS_RIGHT}"


def unglass_text(label: str) -> str:
    """Return the plain label inside the brackets, or the label unchanged.

    Presses made from a keyboard drawn before the style changed still carry the
    old label, so matching strips the decoration instead of assuming it.
    """
    text = (label or "").strip()
    if not (text.startswith(GLASS_LEFT) and text.endswith(GLASS_RIGHT)):
        return text
    inner = text[len(GLASS_LEFT) : -len(GLASS_RIGHT)].strip()
    if GLASS_ICON and inner.startswith(GLASS_ICON):
        inner = inner[len(GLASS_ICON) :].strip()
    return inner
