"""Home reply keyboard builders."""

from telethon import Button
from telethon.tl.types import (
    KeyboardButtonRow,
    KeyboardInlineButtonRow,
    ReplyInlineMarkup,
    ReplyKeyboardMarkup,
)

from app.db.crud.keyboards import KeyboardButtonCRUD
from app.db.crud.panels import PanelsManager
from app.db.crud.settings import SettingsManager
from app.db.crud.user import UserCRUD
from app.db.models.settings import DEFAULT_HOME_MENU_SETTINGS
from app.services.keyboard_glass import glass_mode_active
from app.services.panels.settings import panel_reseller_sale_enabled, panel_shop_sale_enabled
from app.services.panels.trials import trial_offered
from config import ADMIN_ID, DISABLE_UPTIME_BUTTONS, LINK_UPTIME_BUTTONS, WEBAPP_URL

from .common import (
    _get_keyboard_button_config,
    styled_callback_button,
    styled_reply_button,
    styled_simple_webview_button,
    styled_webview_button,
)

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

HOME_BUTTON_KEYS: tuple[str, ...] = tuple(key for row in DEFAULT_HOME_LAYOUT for key in row)

# Callback prefix for the in-chat menu; app.telegram.user.menu answers it.
HOME_CALLBACK_PREFIX = "home:"


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

# Telegram refuses a web-view button on a plain-http address and fails the whole
# message, so the mode can only take effect once the WebApp has a real URL.
MINIAPP_READY = WEBAPP_URL.startswith("https://")


def miniapp_only_active(setting) -> bool:
    """Whether the bot should answer with the mini app instead of its own menu."""
    return MINIAPP_READY and bool(setting and getattr(setting, "miniapp_only_mode", False))


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
    trial_ready = await trial_offered(setting)

    def gate(ok: bool, reason: str) -> str:
        return CONDITION_OK if ok else reason

    if miniapp_only_active(setting):
        # Every menu button is held back by the mode, not by its own switch; the
        # keyboard editor shows that rather than leaving the admin guessing.
        return dict.fromkeys(HOME_BUTTON_KEYS, "miniapp_only") | {"bt.menu_admin_panel": CONDITION_OK}

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
    setting = await SettingsManager().get_settings()
    glass = glass_mode_active(setting)

    menu_my_services, menu_my_services_style = await _get_keyboard_button_config(
        keyboard_crud,
        "bt.menu_my_services",
        "🔑 سرویس های من",
        default_style="primary",
        default_icon=5895443668663275064,
        glass=glass,
    )
    menu_get_trial, menu_get_trial_style = await _get_keyboard_button_config(
        keyboard_crud, "bt.menu_get_trial", "🎁 دریافت تست", glass=glass
    )
    menu_buy_service, menu_buy_service_style = await _get_keyboard_button_config(
        keyboard_crud,
        "bt.menu_buy_service",
        "🛍 خرید سرویس",
        default_style="success",
        default_icon=5373052667671093676,
        glass=glass,
    )

    menu_profile, menu_profile_style = await _get_keyboard_button_config(
        keyboard_crud, "bt.menu_profile", "🙍 پروفایل من", glass=glass
    )
    menu_add_balance, menu_add_balance_style = await _get_keyboard_button_config(
        keyboard_crud, "bt.menu_add_balance", "💰 افزایش موجودی", glass=glass
    )

    menu_support, menu_support_style = await _get_keyboard_button_config(
        keyboard_crud, "bt.menu_support", "☎️ پشتیبانی", glass=glass
    )
    menu_uptime, menu_uptime_style = await _get_keyboard_button_config(
        keyboard_crud, "bt.menu_uptime", "🔋 وضعیت سرویس ها", glass=glass
    )
    menu_help, menu_help_style = await _get_keyboard_button_config(
        keyboard_crud, "bt.menu_help", "📚 راهنما", glass=glass
    )
    menu_advanced_settings, menu_advanced_settings_style = await _get_keyboard_button_config(
        keyboard_crud, "bt.menu_advanced_settings", "⚙️ تنظیمات پیشرفته", glass=glass
    )

    menu_admin_panel, menu_admin_panel_style = await _get_keyboard_button_config(
        keyboard_crud, "bt.menu_admin_panel", "⚙️ پنل مدیریت", glass=glass
    )
    menu_buy_reseller, menu_buy_reseller_style = await _get_keyboard_button_config(
        keyboard_crud, "bt.menu_buy_reseller", "🏢 خرید پنل نمایندگی", default_style="success", glass=glass
    )
    menu_my_resellers, menu_my_resellers_style = await _get_keyboard_button_config(
        keyboard_crud, "bt.menu_my_resellers", "📋 نمایندگی‌های من", default_style="primary", glass=glass
    )

    if miniapp_only_active(setting):
        menu_miniapp, menu_miniapp_style = await _get_keyboard_button_config(
            keyboard_crud, "bt.menu_miniapp", "🚀 ورود به اپلیکیشن", default_style="primary", glass=glass
        )
        # A plain button, not a web-view one: Telegram opens a keyboard-button
        # web app "without sending user information" (keyboardButtonSimpleWebView),
        # so the mini app would land on its own login screen. Pressing this asks
        # the bot for an inline web-view button instead, which does carry the
        # Telegram sign-in.
        if glass:
            # In the chat the button can be an inline web view, which is the one
            # kind Telegram signs, so the app opens straight into the account.
            rows = [[styled_webview_button(menu_miniapp, WEBAPP_URL, menu_miniapp_style)]]
            if user_id in ADMIN_ID:
                rows.append(
                    [
                        styled_callback_button(
                            menu_admin_panel,
                            f"{HOME_CALLBACK_PREFIX}bt.menu_admin_panel",
                            menu_admin_panel_style,
                        )
                    ]
                )
            return ReplyInlineMarkup([KeyboardInlineButtonRow(row) for row in rows])

        rows = [[styled_reply_button(menu_miniapp, menu_miniapp_style)]]
        if user_id in ADMIN_ID:
            rows.append([styled_reply_button(menu_admin_panel, menu_admin_panel_style)])
        return ReplyKeyboardMarkup([KeyboardButtonRow(row) for row in rows], resize=True)

    user_data = await UserCRUD().read_user(user_id=user_id)
    conditions = await home_button_conditions()
    visible = {key: not reason for key, reason in conditions.items()}
    # Conditions that depend on who is looking.
    visible["bt.menu_get_trial"] = visible["bt.menu_get_trial"] and bool(user_data and user_data.tested == 0)
    visible["bt.menu_admin_panel"] = user_id in ADMIN_ID

    def widget(key: str, label: str, style_obj, *, url: str | None = None):
        """One menu button, drawn for whichever keyboard this mode uses.

        In the chat the menu is inline, so a press arrives as a callback rather
        than as the button's text; app.telegram.user.menu turns it back into the
        press the handlers already understand.
        """
        if glass:
            if url:
                return styled_webview_button(label, url, style_obj)
            return styled_callback_button(label, f"{HOME_CALLBACK_PREFIX}{key}", style_obj)
        if url:
            return styled_simple_webview_button(label, url, style_obj)
        return styled_reply_button(label, style_obj)

    widgets = {
        "bt.menu_get_trial": lambda: widget("bt.menu_get_trial", menu_get_trial, menu_get_trial_style),
        "bt.menu_my_services": lambda: widget("bt.menu_my_services", menu_my_services, menu_my_services_style),
        "bt.menu_buy_service": lambda: widget("bt.menu_buy_service", menu_buy_service, menu_buy_service_style),
        "bt.menu_my_resellers": lambda: widget("bt.menu_my_resellers", menu_my_resellers, menu_my_resellers_style),
        "bt.menu_buy_reseller": lambda: widget("bt.menu_buy_reseller", menu_buy_reseller, menu_buy_reseller_style),
        "bt.menu_profile": lambda: widget("bt.menu_profile", menu_profile, menu_profile_style),
        "bt.menu_add_balance": lambda: widget("bt.menu_add_balance", menu_add_balance, menu_add_balance_style),
        "bt.menu_support": lambda: widget("bt.menu_support", menu_support, menu_support_style),
        "bt.menu_uptime": lambda: widget("bt.menu_uptime", menu_uptime, menu_uptime_style, url=LINK_UPTIME_BUTTONS),
        "bt.menu_help": lambda: widget("bt.menu_help", menu_help, menu_help_style),
        "bt.menu_advanced_settings": lambda: widget(
            "bt.menu_advanced_settings", menu_advanced_settings, menu_advanced_settings_style
        ),
        "bt.menu_admin_panel": lambda: widget("bt.menu_admin_panel", menu_admin_panel, menu_admin_panel_style),
    }

    layout = await keyboard_crud.get_home_layout()
    hidden = await keyboard_crud.get_hidden_keys()
    keys_by_row = _layout_rows(layout) if layout else DEFAULT_HOME_LAYOUT

    bhome: list[list] = []
    for row_keys in keys_by_row:
        row = [widgets[key]() for key in row_keys if key not in hidden and visible.get(key) and key in widgets]
        if row:
            bhome.append(row)

    if glass:
        return ReplyInlineMarkup([KeyboardInlineButtonRow(row) for row in bhome])
    return ReplyKeyboardMarkup([KeyboardButtonRow(row) for row in bhome], resize=True)
