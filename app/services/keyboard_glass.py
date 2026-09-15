"""Turn the glassy look on or off for every home button at once.

The glassy look is brackets around the label rather than a Telegram style, and
handlers match an incoming press against the *stored* label. So the switch
rewrites the stored text instead of decorating at draw time: whatever the
keyboard shows is what the database holds, and every existing handler keeps
matching without knowing this feature exists.

Colours are a separate column and are never touched here, which is why this is
a switch of its own rather than another entry in the style dropdown.
"""

from __future__ import annotations

from app.db.crud.keyboards import KeyboardButtonCRUD
from app.db.crud.settings import SettingsManager
from app.telegram.keyboards.registry import KEYBOARD_BUTTON_DEFAULTS, KEYBOARD_BUTTON_TITLES
from app.utils.text.glass import glass_text, unglass_text

# Only the home reply keyboard: inline buttons are matched by callback data, so
# bracketing them would be decoration without meaning, and the admin menus are
# built from fixed labels this switch does not own.
GLASS_KEY_PREFIX = "bt.menu_"


def glass_mode_active(setting) -> bool:
    """Whether every home button should carry the glassy brackets."""
    return bool(setting and getattr(setting, "glass_buttons_mode", False))


def glass_target_keys() -> list[str]:
    known = set(KEYBOARD_BUTTON_DEFAULTS) | set(KEYBOARD_BUTTON_TITLES)
    return sorted(key for key in known if key.startswith(GLASS_KEY_PREFIX))


def _default_label(key: str) -> str:
    return KEYBOARD_BUTTON_DEFAULTS.get(key, KEYBOARD_BUTTON_TITLES.get(key, key))


def glass_label(label: str, *, enabled: bool) -> str:
    """Add or remove the brackets, whatever state the label is already in."""
    plain = unglass_text(label)
    return glass_text(plain) if enabled else plain


async def apply_glass_mode(enabled: bool) -> int:
    """Rewrite every home button label to match the switch; returns how many changed."""
    crud = KeyboardButtonCRUD()
    changed = 0
    for key in glass_target_keys():
        row = await crud.get_button(key)
        current = (row.button_text if row else "") or ""
        target = glass_label(current or _default_label(key), enabled=enabled)
        if target == current:
            continue
        if await crud.set_button(key, button_text=target):
            changed += 1
    return changed


async def sync_glass_mode(setting=None) -> int:
    """Re-apply whatever the stored switch says."""
    if setting is None:
        setting = await SettingsManager().get_settings()
    return await apply_glass_mode(glass_mode_active(setting))
