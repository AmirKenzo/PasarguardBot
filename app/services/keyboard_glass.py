"""The glassy keyboard: the menu drawn inside the chat.

Telegram has no translucency switch. What reads as "glass" is where the buttons
live: an inline keyboard belongs to a message, so the client draws it in the
chat as tinted panels over the wallpaper, while a reply keyboard sits under the
composer in the client's own grey. The bot's settings menu has always looked
that way because it is inline; this switch gives the home menu the same shape.

A press on an inline button arrives as a callback rather than as the button's
text, so the switch also brings a small translator with it — see
``app.telegram.user.menu``. Turning it off restores the reply keyboard and none
of that runs, which is the quickest way back if a menu misbehaves.

Colours the admin set per button are kept; the fallback only reaches buttons
that had no colour of their own, so the menu never shows one plain panel
between coloured ones.
"""

from __future__ import annotations

# Telegram offers three: primary (blue), success (green), danger (red). Blue is
# the neutral one, so it is what an uncoloured button falls back to.
GLASS_FALLBACK_STYLE = "primary"


def glass_mode_active(setting) -> bool:
    """Whether the home menu should be drawn inside the chat, coloured."""
    return bool(setting and getattr(setting, "glass_keyboard_mode", False))
