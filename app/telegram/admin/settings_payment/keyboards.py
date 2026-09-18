"""Keyboard builders for admin settings_payment."""

from telethon import Button

from app.telegram.admin.settings_payment import texts


def btn_cardtocard_settings(settings=None):
    auto_text = "✅ تایید خودکار روشن" if settings and settings.manual_auto_confirm else "❌ تایید خودکار خاموش"
    random_mode_text = (
        "✅ نمایش رندوم کارت روشن" if settings and settings.manual_card_random_mode else "❌ نمایش رندوم کارت خاموش"
    )
    visibility_text = texts.manual_card_visibility_button_label(settings)
    return [
        [
            Button.inline(text="➕ افزودن کارت", data="add_manual_card"),
            Button.inline(text="🗑 حذف کارت", data="delete_manual_card"),
        ],
        [Button.inline(text="📋 انتخاب کارت فعال", data="select_active_card")],
        [Button.inline(text=visibility_text, data="toggle_manual_card_visibility")],
        [Button.inline(text=random_mode_text, data="toggle_manual_card_random_mode")],
        [Button.inline(text=auto_text, data="toggle_manual_auto_confirm")],
        [Button.inline(text="📋 قوانین تایید خودکار", data="maar_rules_menu")],
        [
            Button.inline(text="💰 محدودیت کارت دستی", data="set_manual_limits"),
        ],
        [Button.inline(text="💰 محدودیت واریز ارزی", data="set_crypto_limits")],
        [Button.inline(text="🏷 حداقل شارژ نمایندگی", data="set_reseller_min_wallet")],
        [Button.inline(text="🎁 تنظیمات بونوس", data="bonus_settings_menu")],
        [Button.inline(text="💼 مدیریت کیف پول‌ها", data="wallet_management")],
    ]


def back_to_settings_card_button():
    return [Button.inline("بازگشت به قبل", data="BackTOSettingsCardToCard")]


def back_to_settings_card_row():
    return [[Button.inline("بازگشت", data="BackTOSettingsCardToCard")]]


def back_to_bonus_menu_button():
    return [Button.inline("بازگشت", data="bonus_settings_menu")]


def bonus_settings_buttons(settings):
    return [
        [
            Button.inline(
                f"💳 کارت دستی: {settings.manual_bonus_percent}% {'✅' if settings.manual_bonus_enabled else '❌'}",
                data="toggle_manual_bonus",
            ),
            Button.inline("📝 تنظیم درصد", data="set_manual_bonus_percent"),
        ],
        [
            Button.inline(
                f"💵 ارزی: {settings.crypto_bonus_percent}% {'✅' if settings.crypto_bonus_enabled else '❌'}",
                data="toggle_crypto_bonus",
            ),
            Button.inline("📝 تنظیم درصد", data="set_crypto_bonus_percent"),
        ],
        [
            Button.inline(
                f"⭐ استارز: {settings.stars_bonus_percent}% {'✅' if settings.stars_bonus_enabled else '❌'}",
                data="toggle_stars_bonus",
            ),
            Button.inline("📝 تنظیم درصد", data="set_stars_bonus_percent"),
        ],
        [Button.inline("🔙 بازگشت", data="BackTOSettingsCardToCard")],
    ]


async def get_bonus_settings_menu(settings):
    return texts.bonus_settings_header(settings), bonus_settings_buttons(settings)


def maar_rule_toggle_button(rule):
    return Button.inline(
        f"{'✅' if rule.is_active else '❌'} {texts.maar_range(rule)}",
        f"maar_view:{rule.id}",
    )


def maar_menu_buttons(rules):
    buttons = [[maar_rule_toggle_button(rule)] for rule in rules]
    buttons += [[Button.inline("➕ افزودن", "maar_add")], [Button.inline("🔙 بازگشت", "BackTOSettingsCardToCard")]]
    return buttons


def maar_show_rule_buttons(rule_id: int, rules):
    idx = next(i for i, rule in enumerate(rules) if rule.id == rule_id)
    row = []
    if idx > 0:
        row.append(Button.inline("⬆️", f"maar_up:{rule_id}"))
    if idx < len(rules) - 1:
        row.append(Button.inline("⬇️", f"maar_down:{rule_id}"))
    rows = [row] if row else []
    rows += [
        [Button.inline("حداقل", f"maar_edit_min:{rule_id}"), Button.inline("حداکثر", f"maar_edit_max:{rule_id}")],
        [Button.inline("زمان", f"maar_edit_delay:{rule_id}"), Button.inline("فعال/غیرفعال", f"maar_toggle:{rule_id}")],
        [Button.inline("🗑 حذف", f"maar_delete:{rule_id}")],
        [Button.inline("🔙 لیست", "maar_rules_menu")],
    ]
    return rows


def maar_add_back_button():
    return [Button.inline("🔙", "maar_rules_menu")]


def maar_edit_back_button(rule_id: int):
    return [Button.inline("🔙", f"maar_view:{rule_id}")]


def maar_saved_back_button(rule_id: int):
    return [Button.inline("بازگشت", f"maar_view:{rule_id}")]


def card_list_buttons(cards, callback_prefix: str, active_marker: bool = False):
    buttons = []
    for card in cards:
        label = f"{card.number} - {card.name}{' ✅' if active_marker and card.active else ''}"
        buttons.append([Button.inline(label, f"{callback_prefix}:{card.id}")])
    buttons.append(back_to_settings_card_button())
    return buttons


def no_action_balance_button(new_balance: int):
    return [[Button.inline(text=f"موجودی جدید {new_balance:,} تومان", data="no_action")]]


def tx_review_result_button(approved: bool):
    label = texts.TX_APPROVED_ADMIN_BUTTON if approved else texts.TX_REJECTED_ADMIN_BUTTON
    return [[Button.inline(text=label, data="no_action")]]


def tx_reject_user_balance_button(balance: float):
    return [[Button.inline(text=f"موجودی: {balance:,.0f} تومان", data="no_action")]]


def crypto_limit_back_button():
    return [Button.inline("بازگشت", data="back_to_settings")]


def gateway_settings_buttons(settings):
    return btn_cardtocard_settings(settings)
