"""State constants for admin settings."""

from app.utils.formatting.conversions import as_int

SETTINGS_PANEL_MENU_MESSAGES = frozenset({"📝 متن‌های ربات", "⌨️ مدیریت دکمه‌های کیبورد"})

SETTINGS_ADMIN_STEPS = frozenset({"keyboard_btn_set_icon"})

SETTINGS_CALLBACK_EXACT: frozenset[str] = frozenset()

SETTINGS_CALLBACK_PREFIXES = (
    "edit_keyboard:",
    "keyboard_btn_edit_text:",
    "keyboard_btn_color:",
    "keyboard_btn_icon:",
    "keyboard_btn_icon_clear:",
    "keyboard_page:",
    "text_sections_page:",
    "text_section:",
    "text_keys_page:",
    "edit_text:",
    "reset_text:",
    "confirm_save_text:",
    "cancel_save_text:",
    "edit_banner_url:",
    "set_banner_position:",
)

SETTINGS_MENU_PATTERN = rb"^settings_menu(?::[a-z_]+)?$"
SETTINGS_TOGGLE_PREFIX = "settings."
SETTINGS_MENU_MESSAGE_PATTERN = r"^⚙️ تنظیمات ربات$"
SETTINGS_MENU_TRIGGER = "⚙️ تنظیمات ربات"
PANEL_STEP = "panel"


def parse_stored_page(value, default: int = 1) -> int:
    """Parse page numbers from Redis state (may be int or str after json.loads)."""
    page = as_int(value)
    return page if page is not None and page >= 1 else default
