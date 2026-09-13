"""Home reply keyboard builders."""

from telethon import Button
from telethon.tl.types import KeyboardButtonRow, ReplyKeyboardMarkup

from app.db.crud.keyboards import KeyboardButtonCRUD
from app.db.crud.panels import PanelsManager
from app.db.crud.settings import SettingsManager
from app.db.crud.user import UserCRUD
from app.db.models.settings import DEFAULT_HOME_MENU_SETTINGS
from app.services.panels.settings import panel_reseller_sale_enabled, panel_shop_sale_enabled
from config import ADMIN_ID, DISABLE_UPTIME_BUTTONS, LINK_UPTIME_BUTTONS

from .common import _get_keyboard_button_config, styled_reply_button, styled_simple_webview_button

bhome = [
    [Button.text("🔑 سرویس های من", resize=True), Button.text("🛍 خرید سرویس")],
    [Button.text("🙍 پروفایل من"), Button.text("💰 افزایش موجودی")],
    [Button.text("☎️ پشتیبانی"), Button.text("📚 راهنما")],
]


# Row layout used when the admin has not defined one in the web panel.
DEFAULT_HOME_LAYOUT: tuple[tuple[str, ...], ...] = (
    ("bt.menu_get_trial",),
    ("bt.menu_my_services", "bt.menu_buy_service"),
    ("bt.menu_my_resellers", "bt.menu_buy_reseller"),
    ("bt.menu_profile", "bt.menu_add_balance"),
    ("bt.menu_support", "bt.menu_uptime", "bt.menu_help"),
    ("bt.menu_advanced_settings",),
    ("bt.menu_admin_panel",),
)


def _home_menu_enabled(setting, attr: str) -> bool:
    """Return home-menu toggle value; missing settings default to ON."""
    default = bool(DEFAULT_HOME_MENU_SETTINGS.get(attr, True))
    if setting is None:
        return default
    return bool(getattr(setting, attr, default))


# Reason codes for a home button that cannot render whatever the admin's
# visibility switch says. The web panel shows these so a button held back by
# configuration is not mistaken for a broken switch.
CONDITION_OK = ""


async def home_button_conditions() -> dict[str, str]:
    """Return ``{button key: reason it cannot render}``, empty meaning it can.

    Answers "could this button appear for anyone right now", so per-user state
    (whether this particular user already took a trial, whether they are an
    admin) is deliberately left out — the caller layers that on top.
    """
    setting = await SettingsManager().get_settings()
    panels = await PanelsManager().get_all_panels()
    shop_sale = any(panel_shop_sale_enabled(panel) for panel in panels)
    reseller_sale = bool(setting and setting.reseller_sale_mode) and any(
        panel_reseller_sale_enabled(panel) for panel in panels
    )
    trial_ready = bool(setting and setting.test_mode == 1 and setting.test_panel_id != 0)

    def gate(ok: bool, reason: str) -> str:
        return CONDITION_OK if ok else reason

    return {
        "bt.menu_get_trial": gate(trial_ready, "trial_off"),
        "bt.menu_my_services": gate(shop_sale, "no_shop_panel"),
        "bt.menu_buy_service": gate(shop_sale, "no_shop_panel"),
        "bt.menu_my_resellers": gate(reseller_sale, "reseller_sale_off"),
        "bt.menu_buy_reseller": gate(reseller_sale, "reseller_sale_off"),
        "bt.menu_profile": gate(_home_menu_enabled(setting, "profile_mode"), "setting_off"),
        "bt.menu_add_balance": CONDITION_OK,
        "bt.menu_support": gate(_home_menu_enabled(setting, "support_mode"), "setting_off"),
        "bt.menu_uptime": gate(not DISABLE_UPTIME_BUTTONS, "uptime_disabled"),
        "bt.menu_help": gate(_home_menu_enabled(setting, "help_mode"), "setting_off"),
        "bt.menu_advanced_settings": gate(_home_menu_enabled(setting, "advanced_settings_mode"), "setting_off"),
        "bt.menu_admin_panel": CONDITION_OK,
    }


def _layout_rows(layout: dict[str, tuple[int, int]]) -> list[tuple[str, ...]]:
    """Turn ``{key: (row, order)}`` into an ordered list of rows."""
    rows: dict[int, list[tuple[int, str]]] = {}
    for key, (row_index, order) in layout.items():
        rows.setdefault(row_index, []).append((order, key))
    return [tuple(key for _, key in sorted(items)) for _, items in sorted(rows.items())]


async def bhome_buttons(user_id, lang):
    keyboard_crud = KeyboardButtonCRUD()

    menu_my_services, menu_my_services_style = await _get_keyboard_button_config(
        keyboard_crud,
        "bt.menu_my_services",
        "🔑 سرویس های من",
        default_style="primary",
        default_icon=5895443668663275064,
    )
    menu_get_trial, menu_get_trial_style = await _get_keyboard_button_config(
        keyboard_crud, "bt.menu_get_trial", "🎁 دریافت تست"
    )
    menu_buy_service, menu_buy_service_style = await _get_keyboard_button_config(
        keyboard_crud,
        "bt.menu_buy_service",
        "🛍 خرید سرویس",
        default_style="success",
        default_icon=5373052667671093676,
    )

    menu_profile, menu_profile_style = await _get_keyboard_button_config(
        keyboard_crud, "bt.menu_profile", "🙍 پروفایل من"
    )
    menu_add_balance, menu_add_balance_style = await _get_keyboard_button_config(
        keyboard_crud, "bt.menu_add_balance", "💰 افزایش موجودی"
    )

    menu_support, menu_support_style = await _get_keyboard_button_config(keyboard_crud, "bt.menu_support", "☎️ پشتیبانی")
    menu_uptime, menu_uptime_style = await _get_keyboard_button_config(
        keyboard_crud, "bt.menu_uptime", "🔋 وضعیت سرویس ها"
    )
    menu_help, menu_help_style = await _get_keyboard_button_config(keyboard_crud, "bt.menu_help", "📚 راهنما")
    menu_advanced_settings, menu_advanced_settings_style = await _get_keyboard_button_config(
        keyboard_crud, "bt.menu_advanced_settings", "⚙️ تنظیمات پیشرفته"
    )

    menu_admin_panel, menu_admin_panel_style = await _get_keyboard_button_config(
        keyboard_crud, "bt.menu_admin_panel", "⚙️ پنل مدیریت"
    )
    menu_buy_reseller, menu_buy_reseller_style = await _get_keyboard_button_config(
        keyboard_crud,
        "bt.menu_buy_reseller",
        "🏢 خرید پنل نمایندگی",
        default_style="success",
    )
    menu_my_resellers, menu_my_resellers_style = await _get_keyboard_button_config(
        keyboard_crud,
        "bt.menu_my_resellers",
        "📋 نمایندگی‌های من",
        default_style="primary",
    )

    user_data = await UserCRUD().read_user(user_id=user_id)
    conditions = await home_button_conditions()
    visible = {key: not reason for key, reason in conditions.items()}
    # Conditions that depend on who is looking.
    visible["bt.menu_get_trial"] = visible["bt.menu_get_trial"] and bool(user_data and user_data.tested == 0)
    visible["bt.menu_admin_panel"] = user_id in ADMIN_ID
    widgets = {
        "bt.menu_get_trial": lambda: styled_reply_button(menu_get_trial, menu_get_trial_style),
        "bt.menu_my_services": lambda: styled_reply_button(menu_my_services, menu_my_services_style),
        "bt.menu_buy_service": lambda: styled_reply_button(menu_buy_service, menu_buy_service_style),
        "bt.menu_my_resellers": lambda: styled_reply_button(menu_my_resellers, menu_my_resellers_style),
        "bt.menu_buy_reseller": lambda: styled_reply_button(menu_buy_reseller, menu_buy_reseller_style),
        "bt.menu_profile": lambda: styled_reply_button(menu_profile, menu_profile_style),
        "bt.menu_add_balance": lambda: styled_reply_button(menu_add_balance, menu_add_balance_style),
        "bt.menu_support": lambda: styled_reply_button(menu_support, menu_support_style),
        "bt.menu_uptime": lambda: styled_simple_webview_button(menu_uptime, LINK_UPTIME_BUTTONS, menu_uptime_style),
        "bt.menu_help": lambda: styled_reply_button(menu_help, menu_help_style),
        "bt.menu_advanced_settings": lambda: styled_reply_button(menu_advanced_settings, menu_advanced_settings_style),
        "bt.menu_admin_panel": lambda: styled_reply_button(menu_admin_panel, menu_admin_panel_style),
    }

    layout = await keyboard_crud.get_home_layout()
    hidden = await keyboard_crud.get_hidden_keys()
    keys_by_row = _layout_rows(layout) if layout else DEFAULT_HOME_LAYOUT

    bhome: list[list] = []
    for row_keys in keys_by_row:
        row = [widgets[key]() for key in row_keys if key not in hidden and visible.get(key) and key in widgets]
        if row:
            bhome.append(row)

    return ReplyKeyboardMarkup([KeyboardButtonRow(button) for button in bhome], resize=True)
