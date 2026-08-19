"""Admin UI for editing configurable keyboard buttons."""

from telethon import Button

from app.db.crud.keyboards import KeyboardButtonCRUD

from .common import _get_keyboard_button_config, styled_callback_button
from .registry import (
    KEYBOARD_BUTTON_DEFAULT_STYLES,
    KEYBOARD_BUTTON_DEFAULTS,
    KEYBOARD_BUTTON_TITLES,
    STYLE_LABELS,
)


async def _keyboard_admin_button(keyboard_crud: KeyboardButtonCRUD, button_key: str, page: int):
    default_style, default_icon = KEYBOARD_BUTTON_DEFAULT_STYLES.get(button_key, (None, None))
    text, style_obj = await _get_keyboard_button_config(
        keyboard_crud,
        button_key,
        KEYBOARD_BUTTON_DEFAULTS.get(button_key, KEYBOARD_BUTTON_TITLES.get(button_key, button_key)),
        default_style=default_style,
        default_icon=default_icon,
    )
    return styled_callback_button(text, f"edit_keyboard:{button_key}:{page}", style_obj)


def keyboard_button_config_text(button_key: str, button_obj) -> str:
    pretty = KEYBOARD_BUTTON_TITLES.get(button_key, button_key)
    current_text = getattr(button_obj, "button_text", None)
    current_style = STYLE_LABELS.get(getattr(button_obj, "button_style", None), "بدون رنگ")
    current_icon = getattr(button_obj, "button_icon", None) or "ندارد"
    return (
        f"⌨️ **تنظیم دکمه «{pretty}»**\n\n"
        f"📝 متن فعلی: {current_text or 'ثبت نشده'}\n"
        f"🎨 رنگ فعلی: {current_style}\n"
        f"🖼 آیکون فعلی: {current_icon}\n\n"
        "یکی از گزینه‌های زیر را انتخاب کنید:"
    )


def create_keyboard_button_config_submenu(button_key: str, page: int) -> list:
    return [
        [Button.inline("✏️ متن دکمه", data=f"keyboard_btn_edit_text:{button_key}:{page}")],
        [
            Button.inline("آبی", data=f"keyboard_btn_color:{button_key}:{page}:primary"),
            Button.inline("سبز", data=f"keyboard_btn_color:{button_key}:{page}:success"),
            Button.inline("قرمز", data=f"keyboard_btn_color:{button_key}:{page}:danger"),
            Button.inline("—", data=f"keyboard_btn_color:{button_key}:{page}:none"),
        ],
        [Button.inline("🖼 آیکون ایموجی پریمیوم", data=f"keyboard_btn_icon:{button_key}:{page}")],
        [Button.inline("🧹 حذف آیکون", data=f"keyboard_btn_icon_clear:{button_key}:{page}")],
        [Button.inline("🔙 بازگشت", data=f"keyboard_page:{page}")],
    ]


async def create_keyboard_button_config_view(
    button_key: str, page: int, keyboard_crud: KeyboardButtonCRUD | None = None
):
    keyboard_crud = keyboard_crud or KeyboardButtonCRUD()
    button_obj = await keyboard_crud.get_button(button_key)
    return keyboard_button_config_text(button_key, button_obj), create_keyboard_button_config_submenu(button_key, page)


def generate_location_buttons(code):
    locations = [["🇺🇸 USA", "🇬🇧 UK"], ["🇨🇦 Canada", "🇦🇺 Australia"]]
    return [[Button.inline(loc, f"loc_{code}_{loc}") for loc in row] for row in locations]


async def create_keyboard_buttons_admin_buttons(page: int = 1):
    """
    Create text management buttons keyboard buttons with professional layout

    Args:
        page: page number (1: home, 2: my-services, 3: balance, 4: buy, 5: inline)

    Returns:
    List of paginated buttons
    """
    buttons = []
    keyboard_crud = KeyboardButtonCRUD()

    if page == 1:
        buttons.extend(
            [
                [Button.inline("📋 ━━━━ دکمه‌های منوی اصلی ━━━━", data="no_action")],
                [await _keyboard_admin_button(keyboard_crud, "bt.menu_get_trial", 1)],
                [
                    await _keyboard_admin_button(keyboard_crud, "bt.menu_my_services", 1),
                    await _keyboard_admin_button(keyboard_crud, "bt.menu_buy_service", 1),
                ],
                [
                    await _keyboard_admin_button(keyboard_crud, "bt.menu_my_resellers", 1),
                    await _keyboard_admin_button(keyboard_crud, "bt.menu_buy_reseller", 1),
                ],
                [
                    await _keyboard_admin_button(keyboard_crud, "bt.menu_profile", 1),
                    await _keyboard_admin_button(keyboard_crud, "bt.menu_add_balance", 1),
                ],
                [
                    await _keyboard_admin_button(keyboard_crud, "bt.menu_support", 1),
                    await _keyboard_admin_button(keyboard_crud, "bt.menu_uptime", 1),
                    await _keyboard_admin_button(keyboard_crud, "bt.menu_help", 1),
                ],
                [await _keyboard_admin_button(keyboard_crud, "bt.menu_advanced_settings", 1)],
                [await _keyboard_admin_button(keyboard_crud, "bt.menu_admin_panel", 1)],
            ]
        )

        navigation = []
        navigation.append(Button.inline("➡️ صفحه بعدی", data="keyboard_page:2"))
        if navigation:
            buttons.append(navigation)

    elif page == 2:
        buttons.extend(
            [
                [Button.inline("📋 ━━━━ دکمه‌های بخش سرویس ━━━━", data="no_action")],
                [
                    await _keyboard_admin_button(keyboard_crud, "in.ms.change_link", 2),
                    await _keyboard_admin_button(keyboard_crud, "in.ms.change_sub", 2),
                    await _keyboard_admin_button(keyboard_crud, "in.ms.copy_link", 2),
                ],
                [await _keyboard_admin_button(keyboard_crud, "in.ms.info", 2)],
                [
                    await _keyboard_admin_button(keyboard_crud, "in.ms.extra_volume", 2),
                    await _keyboard_admin_button(keyboard_crud, "in.ms.extend_time", 2),
                ],
                [
                    await _keyboard_admin_button(keyboard_crud, "in.ms.extend_service", 2),
                ],
                [await _keyboard_admin_button(keyboard_crud, "in.ms.qrcode", 2)],
                [
                    await _keyboard_admin_button(keyboard_crud, "in.ms.transfer_config", 2),
                    await _keyboard_admin_button(keyboard_crud, "in.ms.other_links", 2),
                ],
                [await _keyboard_admin_button(keyboard_crud, "in.ms.show_clients", 2)],
                [await _keyboard_admin_button(keyboard_crud, "in.ms.usage_chart", 2)],
                [await _keyboard_admin_button(keyboard_crud, "in.ms.delete_service", 2)],
                [await _keyboard_admin_button(keyboard_crud, "in.ms.back_to_services", 2)],
                [Button.inline("📋 ━━━━ تأیید نهایی تمدید اکانت ━━━━", data="no_action")],
                [
                    await _keyboard_admin_button(keyboard_crud, "in.ms.renew.discount", 2),
                    await _keyboard_admin_button(keyboard_crud, "in.ms.renew.confirm", 2),
                ],
                [await _keyboard_admin_button(keyboard_crud, "in.ms.renew.back", 2)],
                [Button.inline("📋 ━━━━ لینک‌های دیگر (othersSubLinks) ━━━━", data="no_action")],
                [
                    await _keyboard_admin_button(keyboard_crud, "in.ms.sub_links.prev", 2),
                    await _keyboard_admin_button(keyboard_crud, "in.ms.sub_links.next", 2),
                ],
                [
                    await _keyboard_admin_button(keyboard_crud, "in.ms.sub_links.get_all", 2),
                    await _keyboard_admin_button(keyboard_crud, "in.ms.sub_links.back", 2),
                ],
            ]
        )

        navigation = []
        navigation.append(Button.inline("⬅️ صفحه قبلی", data="keyboard_page:1"))
        navigation.append(Button.inline("➡️ صفحه بعدی", data="keyboard_page:3"))
        if navigation:
            buttons.append(navigation)

    elif page == 3:
        buttons.extend(
            [
                [Button.inline("📋 ━━━━ دکمه‌های افزایش موجودی ━━━━", data="no_action")],
                [
                    await _keyboard_admin_button(keyboard_crud, "in.balance.crypto", 3),
                    await _keyboard_admin_button(keyboard_crud, "in.balance.manual", 3),
                ],
                [await _keyboard_admin_button(keyboard_crud, "in.balance.referral", 3)],
                [await _keyboard_admin_button(keyboard_crud, "in.balance.back_home", 3)],
                [await _keyboard_admin_button(keyboard_crud, "in.balance.disabled", 3)],
                [Button.inline("📋 ━━━━ زیرمنوی پرداخت ارزی ━━━━", data="no_action")],
                [
                    await _keyboard_admin_button(keyboard_crud, "in.balance.trx", 3),
                    await _keyboard_admin_button(keyboard_crud, "in.balance.usdt", 3),
                ],
                [
                    await _keyboard_admin_button(keyboard_crud, "in.balance.ton", 3),
                    await _keyboard_admin_button(keyboard_crud, "in.balance.crypto_back", 3),
                ],
                [Button.inline("📋 ━━━━ کارت به کارت دستی ━━━━", data="no_action")],
                [
                    await _keyboard_admin_button(keyboard_crud, "in.balance.send_receipt", 3),
                    await _keyboard_admin_button(keyboard_crud, "in.balance.flow_cancel", 3),
                ],
            ]
        )

        navigation = []
        navigation.append(Button.inline("⬅️ صفحه قبلی", data="keyboard_page:2"))
        navigation.append(Button.inline("➡️ صفحه بعدی", data="keyboard_page:4"))
        if navigation:
            buttons.append(navigation)

    elif page == 4:
        buttons.extend(
            [
                [Button.inline("📋 ━━━━ دکمه‌های خرید سرویس ━━━━", data="no_action")],
                [
                    await _keyboard_admin_button(keyboard_crud, "in.buy.cancel", 4),
                    await _keyboard_admin_button(keyboard_crud, "in.buy.back", 4),
                ],
                [
                    await _keyboard_admin_button(keyboard_crud, "in.buy.confirm", 4),
                    await _keyboard_admin_button(keyboard_crud, "in.buy.discount", 4),
                ],
                [
                    await _keyboard_admin_button(keyboard_crud, "in.buy.default_username", 4),
                    await _keyboard_admin_button(keyboard_crud, "in.buy.retry_username", 4),
                ],
                [await _keyboard_admin_button(keyboard_crud, "in.buy.custom", 4)],
                [
                    await _keyboard_admin_button(keyboard_crud, "in.buy.empty_list", 4),
                ],
            ]
        )

        navigation = []
        navigation.append(Button.inline("⬅️ صفحه قبلی", data="keyboard_page:3"))
        navigation.append(Button.inline("➡️ صفحه بعدی", data="keyboard_page:5"))
        if navigation:
            buttons.append(navigation)

    elif page == 5:
        buttons.extend(
            [
                [Button.inline("📋 ━━━━ دکمه‌های نمایندگی ━━━━", data="no_action")],
                [
                    await _keyboard_admin_button(keyboard_crud, "in.rs.show_creds", 5),
                    await _keyboard_admin_button(keyboard_crud, "in.rs.change_password", 5),
                ],
                [
                    await _keyboard_admin_button(keyboard_crud, "in.rs.resume", 5),
                    await _keyboard_admin_button(keyboard_crud, "in.rs.pause", 5),
                ],
                [
                    await _keyboard_admin_button(keyboard_crud, "in.rs.renew", 5),
                    await _keyboard_admin_button(keyboard_crud, "in.rs.usage_report", 5),
                ],
                [
                    await _keyboard_admin_button(keyboard_crud, "in.rs.usage_cap", 5),
                    await _keyboard_admin_button(keyboard_crud, "in.rs.usage_cap_set", 5),
                ],
                [
                    await _keyboard_admin_button(keyboard_crud, "in.rs.usage_cap_clear", 5),
                    await _keyboard_admin_button(keyboard_crud, "in.rs.delete", 5),
                ],
                [
                    await _keyboard_admin_button(keyboard_crud, "in.rs.buy_user_capacity", 5),
                    await _keyboard_admin_button(keyboard_crud, "in.rs.buy_random_username", 5),
                ],
                [
                    await _keyboard_admin_button(keyboard_crud, "in.rs.delete_confirm", 5),
                ],
                [
                    await _keyboard_admin_button(keyboard_crud, "in.rs.chpwd_confirm", 5),
                ],
            ]
        )

        navigation = []
        navigation.append(Button.inline("⬅️ صفحه قبلی", data="keyboard_page:4"))
        if navigation:
            buttons.append(navigation)

    buttons.append([Button.inline("🔙 بازگشت به پنل", data="back_to_admin_panel")])

    return buttons
