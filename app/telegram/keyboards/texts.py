"""Bot-text management keyboards."""

from telethon import Button
from telethon.extensions import html as html_ext

from app import Kenzo
from app.db.crud.bot_texts import BotTextCRUD


def render_stored_text_html(value: str | None) -> str:
    """Convert a stored bot-text value (our custom markdown, incl. premium emoji) into
    safe HTML so it renders correctly when embedded inside an HTML-parsed admin message."""
    if not value:
        return ""
    clean_text, entities = Kenzo.parse_mode.parse(value)
    return html_ext.unparse(clean_text, entities)


TEXT_SECTIONS = {
    "start": {"name": "پیام استارت", "icon": "🚀"},
    "my_services": {"name": "سرویس‌های من", "icon": "🔑"},
    "buy_service": {"name": "خرید سرویس", "icon": "🛍"},
    "balance": {"name": "افزایش موجودی", "icon": "💰"},
    "manual_card": {"name": "کارت به کارت", "icon": "💳"},
    "crypto_payment": {"name": "پرداخت ارزی", "icon": "💵"},
    "webhook": {"name": "اطلاع‌رسانی", "icon": "🔔"},
    "renewal": {"name": "تمدید سرویس", "icon": "🔄"},
    "reseller": {"name": "نمایندگی", "icon": "🏢"},
    "other": {"name": "سایر", "icon": "📝"},
    "reserved_1": {"name": "رزرو 1", "icon": "🔲"},
    "reserved_2": {"name": "رزرو 2", "icon": "🔲"},
    "reserved_3": {"name": "رزرو 3", "icon": "🔲"},
}

TEXT_KEYS_CONFIG = {
    "start": [
        {"key": "start_message", "title": "پیام استارت", "placeholders": {}},
    ],
    "my_services": [
        {"key": "my_services_intro", "title": "متن معرفی سرویس‌های من", "placeholders": {}},
        {"key": "no_services_message", "title": "پیام عدم وجود سرویس", "placeholders": {}},
        {"key": "no_services_message_button", "title": "دکمه خرید سرویس", "placeholders": {}},
        {
            "key": "service_info_message",
            "title": "متن اطلاعات سرویس",
            "placeholders": {
                "status": "وضعیت سرویس",
                "ip_limit": "محدودیت کاربر و دستگاه",
                "plan_name": "نام پلان",
                "service_code": "کد سرویس",
                "config_name": "اسم کانفیگ",
                "used_volume": "حجم مصرفی",
                "lifetime_used_traffic": "حجم کل مصرفی (بدون ریست)",
                "usage_progress": "نوار درصد مصرف حجم",
                "remaining_volume": "حجم باقی مانده",
                "total_volume": "حجم سرویس",
                "reset_info": "اطلاعات ریست (اختیاری)",
                "expiry_date": "تاریخ انقضا",
                "last_connection": "آخرین اتصال (اختیاری)",
                "edit_at": "آخرین ویرایش کانفیگ (اختیاری)",
                "subscription_url": "لینک سابسکریپشن",
                "tunnel_subscription_url": "لینک تانل شده ساب (اختیاری)",
            },
        },
    ],
    "buy_service": [
        {"key": "buy_service_intro", "title": "متن معرفی خرید سرویس", "placeholders": {}},
        {
            "key": "buy_select_panel_volume_message",
            "title": "متن انتخاب حجم پنل",
            "placeholders": {"panel_name": "نام پنل"},
        },
        {"key": "buy_select_duration_message", "title": "متن انتخاب مدت زمان", "placeholders": {}},
        {
            "key": "custom_buy_enter_gb_message",
            "title": "خرید دلخواه — وارد کردن حجم",
            "placeholders": {
                "panel_name": "نام پنل",
                "price_per_gb": "قیمت هر گیگ",
                "price_per_day": "قیمت هر روز",
                "min_gb": "حداقل حجم",
                "max_gb": "حداکثر حجم",
            },
        },
        {
            "key": "custom_buy_enter_days_message",
            "title": "خرید دلخواه — وارد کردن زمان",
            "placeholders": {
                "gb": "حجم انتخاب‌شده",
                "min_days": "حداقل روز",
                "max_days": "حداکثر روز",
            },
        },
        {"key": "enter_username_message", "title": "متن وارد کردن نام کاربری", "placeholders": {}},
        {
            "key": "buy_username_conflict_message",
            "title": "پیام نام تکراری کانفیگ",
            "placeholders": {"username": "نام کانفیگ تکراری"},
        },
        {
            "key": "buy_username_conflict_alert",
            "title": "نوتیف نام تکراری کانفیگ",
            "placeholders": {"username": "نام کانفیگ تکراری"},
        },
        {
            "key": "config_purchase_confirm",
            "title": "پیام تأیید خرید کانفیگ",
            "placeholders": {
                "volume": "حجم سرویس",
                "duration": "مدت زمان",
                "config_name": "نام کانفیگ",
                "config_type": "نوع کانفیگ",
                "locations": "لوکیشن های موجود",
                "user_limit": "محدودیت کاربر",
                "price": "قیمت نهایی",
            },
        },
        {
            "key": "config_purchase_success_message",
            "title": "پیام موفقیت خرید کانفیگ",
            "placeholders": {
                "creation_time": "زمان ساخت",
                "service_code": "کد سرویس",
                "account_name": "اسم کانفیگ",
                "volume": "حجم انتخابی",
                "duration": "مدت زمان",
                "user_limit": "محدودیت کاربر",
                "subscription_url": "لینک سابسکریپشن",
                "config_links": "لینک‌های تکی انتخاب‌شده",
                "config_links_with_txt": "بخش آماده لینک‌های تکی با عنوان",
                "amount_deducted": "مبلغ کسر شده",
                "new_balance": "موجودی جدید",
            },
        },
        {
            "key": "test_config_delivery_message",
            "title": "پیام تحویل کانفیگ تست",
            "placeholders": {
                "creation_time": "زمان ساخت",
                "service_code": "کد سرویس",
                "account_name": "اسم کانفیگ",
                "test_volume": "حجم تست",
                "test_duration": "مدت زمان تست",
                "subscription_url": "لینک سابسکریپشن",
                "config_links": "لینک‌های تکی انتخاب‌شده",
                "config_links_with_txt": "بخش آماده لینک‌های تکی با عنوان",
            },
        },
        {
            "key": "config_purchase_discount_confirm",
            "title": "پیام تأیید خرید با کد تخفیف",
            "placeholders": {
                "volume": "حجم سرویس",
                "duration": "مدت زمان",
                "config_name": "نام کانفیگ",
                "config_type": "نوع کانفیگ",
                "locations": "لوکیشن های موجود",
                "user_limit": "محدودیت کاربر",
                "original_price": "مبلغ قبل از تخفیف",
                "new_price": "مبلغ جدید",
            },
        },
    ],
    "reseller": [
        {"key": "reseller_my_list_intro", "title": "متن لیست نمایندگی‌های من", "placeholders": {"count": "تعداد"}},
        {"key": "reseller_my_list_empty", "title": "پیام نبودن نمایندگی", "placeholders": {}},
        {"key": "reseller_buy_panel_picker", "title": "متن انتخاب پنل (خرید)", "placeholders": {}},
        {"key": "reseller_select_plan_prompt", "title": "متن انتخاب پلن", "placeholders": {"panel_name": "نام پنل"}},
    ],
    "balance": [
        {"key": "add_balance_intro", "title": "متن معرفی افزایش موجودی", "placeholders": {}},
        {
            "key": "insufficient_balance_message",
            "title": "پیام کمبود موجودی (حالت عادی)",
            "placeholders": {
                "required": "مبلغ لازم",
                "shortfall": "کمبود موجودی",
                "product_label": "نام محصول",
                "volume": "حجم",
                "balance": "موجودی فعلی",
            },
        },
        {
            "key": "insufficient_balance_direct_pay",
            "title": "پیام کمبود موجودی (پرداخت مستقیم)",
            "placeholders": {
                "required": "مبلغ لازم",
                "shortfall": "کمبود موجودی",
                "product_label": "نام محصول",
                "volume": "حجم",
                "balance": "موجودی فعلی",
            },
        },
        {
            "key": "insufficient_balance_direct_pay_renew",
            "title": "پیام کمبود موجودی (پرداخت مستقیم تمدید)",
            "placeholders": {
                "required": "مبلغ لازم",
                "shortfall": "کمبود موجودی",
                "product_label": "نام محصول",
                "volume": "حجم",
                "balance": "موجودی فعلی",
            },
        },
        {
            "key": "direct_pay_topup_intro",
            "title": "معرفی پرداخت مستقیم پس از کلیک افزایش موجودی",
            "placeholders": {
                "product_label": "نام محصول",
                "volume": "حجم",
                "topup_amount": "مبلغ شارژ",
                "required": "مبلغ کل خرید",
                "shortfall": "کمبود موجودی",
            },
        },
        {
            "key": "direct_pay_renew_topup_intro",
            "title": "معرفی پرداخت مستقیم تمدید پس از کلیک افزایش موجودی",
            "placeholders": {
                "product_label": "نام محصول",
                "volume": "حجم",
                "topup_amount": "مبلغ شارژ",
                "required": "مبلغ کل تمدید",
                "shortfall": "کمبود موجودی",
            },
        },
        {
            "key": "direct_pay_fulfill_failed",
            "title": "خطای ساخت خودکار پس از شارژ",
            "placeholders": {"balance": "موجودی فعلی"},
        },
        {
            "key": "direct_pay_renew_fulfill_failed",
            "title": "خطای تمدید خودکار پس از شارژ",
            "placeholders": {"balance": "موجودی فعلی"},
        },
        {
            "key": "direct_pay_cancelled",
            "title": "لغو سفارش پرداخت مستقیم",
            "placeholders": {},
        },
    ],
    "manual_card": [
        {
            "key": "manual_card_info",
            "title": "متن اطلاعات واریز (بعد از ثبت مبلغ)",
            "placeholders": {
                "min_amount": "حداقل شارژ (تومان)",
                "max_amount": "حداکثر شارژ (تومان)",
                "amount": "مبلغ تومان",
                "amount_toman": "مبلغ تومان",
                "amount_rial": "مبلغ ریال",
                "card_line": "شماره کارت (اختیاری / قدیمی)",
            },
        },
        {
            "key": "manual_card_amount_request",
            "title": "متن درخواست مبلغ",
            "placeholders": {
                "min_amount": "حداقل شارژ (تومان)",
                "max_amount": "حداکثر شارژ (تومان)",
            },
        },
        {
            "key": "manual_card_receipt_request",
            "title": "متن درخواست رسید",
            "placeholders": {
                "amount": "مبلغ تومان",
                "amount_toman": "مبلغ تومان",
                "amount_rial": "مبلغ ریال",
            },
        },
        {
            "key": "manual_card_receipt_confirmed",
            "title": "متن تایید رسید",
            "placeholders": {"amount": "مبلغ"},
        },
        {
            "key": "manual_card_amount_range_error",
            "title": "خطای بازه مبلغ",
            "placeholders": {
                "min_amount": "حداقل شارژ (تومان)",
                "max_amount": "حداکثر شارژ (تومان)",
            },
        },
        {
            "key": "manual_card_numeric_error",
            "title": "خطای ورودی غیرعددی",
            "placeholders": {},
        },
    ],
    "crypto_payment": [
        {
            "key": "crypto_amount_range_error",
            "title": "خطای بازه مبلغ",
            "placeholders": {
                "min_amount": "حداقل شارژ (تومان)",
                "max_amount": "حداکثر شارژ (تومان)",
            },
        },
        {
            "key": "crypto_numeric_error",
            "title": "خطای ورودی غیرعددی",
            "placeholders": {},
        },
    ],
    "webhook": [
        {"key": "webhook_notification_data_exhausted", "title": "اطلاع‌رسانی اتمام حجم", "placeholders": {}},
    ],
    "renewal": [
        {"key": "renewal_step_one_text", "title": "متن مرحله اول تمدید", "placeholders": {}},
        {
            "key": "renewal_step_two_text",
            "title": "متن مرحله دوم تمدید",
            "placeholders": {
                "panel_name": "نام پنل",
                "duration": "مدت زمان انتخابی",
            },
        },
        {
            "key": "renewal_final_step_text",
            "title": "متن مرحله نهایی تمدید",
            "placeholders": {
                "service_code": "کد سرویس",
                "plan_name": "پلن انتخابی",
                "current_remaining_volume": "حجم باقیمانده الان",
                "new_remaining_volume": "حجم باقیمانده بعد تمدید",
                "duration": "مدت زمان بعد تمدید",
                "ip_limit": "محدودیت کاربر",
                "price": "قیمت نهایی",
            },
        },
        {
            "key": "renewal_success_text",
            "title": "متن موفقیت تمدید",
            "placeholders": {
                "service_code": "کد سرویس",
                "config_name": "نام کانفیگ",
                "plan_name": "پلن انتخابی",
                "new_volume": "حجم جدید",
                "expiration_date": "تاریخ انقضا",
                "price": "مبلغ کسر شده",
                "new_balance": "موجودی جدید",
            },
        },
    ],
    "other": [
        {"key": "help_message", "title": "متن راهنما", "placeholders": {}},
        {"key": "support_message", "title": "متن پشتیبانی", "placeholders": {}},
        {"key": "advanced_settings_intro", "title": "متن تنظیمات پیشرفته", "placeholders": {}},
    ],
    "reserved_1": [],
    "reserved_2": [],
    "reserved_3": [],
}


def create_text_sections_buttons(page: int = 1, per_page: int = 8) -> list:
    """Create paginated buttons for text sections"""
    sections_list = list(TEXT_SECTIONS.items())
    total_sections = len(sections_list)
    num_pages = (total_sections + per_page - 1) // per_page

    start_index = (page - 1) * per_page
    end_index = start_index + per_page
    current_sections = sections_list[start_index:end_index]

    buttons = []
    buttons.append([Button.inline("📝 ━━━━ بخش‌های مدیریت متن ━━━━", data="no_action")])

    for section_key, section_info in current_sections:
        buttons.append(
            [Button.inline(f"{section_info['icon']} {section_info['name']}", data=f"text_section:{section_key}:1")]
        )

    navigation = []
    if page > 1:
        navigation.append(Button.inline("⬅️ صفحه قبلی", data=f"text_sections_page:{page - 1}"))
    if page < num_pages:
        navigation.append(Button.inline("صفحه بعدی ➡️", data=f"text_sections_page:{page + 1}"))
    if navigation:
        buttons.append(navigation)

    buttons.append([Button.inline("🔙 بازگشت به پنل", data="back_to_admin_panel")])
    return buttons


def create_text_keys_buttons(section: str, page: int = 1, per_page: int = 10, sections_page: int = 1) -> list:
    """Create paginated buttons for text keys in a section"""
    if section not in TEXT_KEYS_CONFIG:
        return [[Button.inline("❌ بخش نامعتبر", data=f"text_sections_page:{sections_page}")]]

    keys_list = TEXT_KEYS_CONFIG[section]
    total_keys = len(keys_list)
    num_pages = (total_keys + per_page - 1) // per_page

    start_index = (page - 1) * per_page
    end_index = start_index + per_page
    current_keys = keys_list[start_index:end_index]

    section_info = TEXT_SECTIONS.get(section, {"name": section, "icon": "📝"})
    buttons = []
    buttons.append([Button.inline(f"{section_info['icon']} ━━━━ {section_info['name']} ━━━━", data="no_action")])

    for key_config in current_keys:
        buttons.append([Button.inline(f"✏️ {key_config['title']}", data=f"edit_text:{key_config['key']}")])

    navigation = []
    if page > 1:
        navigation.append(Button.inline("⬅️ صفحه قبلی", data=f"text_keys_page:{section}:{page - 1}:{sections_page}"))
    if page < num_pages:
        navigation.append(Button.inline("صفحه بعدی ➡️", data=f"text_keys_page:{section}:{page + 1}:{sections_page}"))
    if navigation:
        buttons.append(navigation)

    buttons.append([Button.inline("🔙 بازگشت به بخش‌ها", data=f"text_sections_page:{sections_page}")])
    return buttons


def create_bot_texts_admin_buttons():
    """Legacy function - redirects to new section-based UI"""
    return create_text_sections_buttons(page=1)


def create_language_select_buttons(key: str, sections_page: int = 1, section_key: str | None = None):
    back_button_data = (
        f"text_section:{section_key}:1:{sections_page}" if section_key else f"text_sections_page:{sections_page}"
    )
    return [
        [Button.inline("🇮🇷 فارسی", data=f"edit_text:{key}:fa:{sections_page}")],
        [Button.inline("🇬🇧 English", data=f"edit_text:{key}:en:{sections_page}")],
        [Button.inline("🔙 بازگشت", data=back_button_data)],
    ]


async def build_edit_text_view(
    key: str, lang_code: str, sections_page: int, current_val: str | None = None
) -> tuple[str, list]:
    """
    Build the edit text view message and buttons.
    Returns (message_text, buttons)
    """
    bot_text_obj = await BotTextCRUD().get_bot_text(key=key, lang=lang_code)
    if current_val is None:
        current_val = bot_text_obj.value if bot_text_obj else None
    banner_url = bot_text_obj.banner_url if bot_text_obj else None
    banner_position = bot_text_obj.banner_position if bot_text_obj else None

    key_config = None
    section_key = None
    for sec, keys_list in TEXT_KEYS_CONFIG.items():
        for kc in keys_list:
            if kc["key"] == key:
                key_config = kc
                section_key = sec
                break
        if key_config:
            break

    pretty = key_config["title"] if key_config else key
    placeholders = key_config.get("placeholders", {}) if key_config else {}

    placeholder_info = ""
    if placeholders:
        placeholder_list = "\n".join([f"• <code>{{{ph}}}</code>: {desc}" for ph, desc in placeholders.items()])
        placeholder_info = f"\n\n<b>🔧 پلیس‌هولدر های موجود:</b>\n{placeholder_list}\n\n💡 می‌توانید از این پلیس‌هولدر ها در متن خود استفاده کنید."
    else:
        placeholder_info = "\n\nℹ️ این متن پلیس‌هولدر ندارد."

    banner_info = ""
    if banner_url:
        position_text = "بالا" if banner_position == "top" else "پایین" if banner_position == "bottom" else "ست نشده"
        banner_info = f"\n\n<b>🖼️ بنر:</b>\n• لینک: `{banner_url}`\n• موقعیت: {position_text}"
    else:
        banner_info = "\n\n<b>🖼️ بنر:</b> ست نشده"

    if current_val:
        preview = (
            f"📝 متن فعلی ({'فارسی' if lang_code == 'fa' else 'انگلیسی'}):\n"
            f"<blockquote expandable>{render_stored_text_html(current_val)}</blockquote>"
            f"{banner_info}"
            f"{placeholder_info}\n\n"
            f"<b>لطفاً متن جدید برای «{pretty}» را ارسال کنید یا یکی از گزینه‌های زیر را انتخاب کنید.</b>"
        )
    else:
        preview = (
            f"⚠️ برای این زبان هنوز متنی ست نشده است."
            f"{banner_info}"
            f"{placeholder_info}\n\n"
            f"<b>لطفاً متن جدید برای «{pretty}» را ارسال کنید یا یکی از گزینه‌های زیر را انتخاب کنید.</b>"
        )

    buttons = [
        [Button.inline("🖼️ تغییر لینک بنر", data=f"edit_banner_url:{key}:{lang_code}:{sections_page}")],
        [Button.inline("🔄 ریست به پیش‌فرض", data=f"reset_text:{key}:{lang_code}:{sections_page}")],
    ]
    if section_key:
        buttons.append([Button.inline("🔙 بازگشت", data=f"text_section:{section_key}:1:{sections_page}")])
    else:
        buttons.append([Button.inline("🔙 بازگشت", data=f"text_sections_page:{sections_page}")])

    return preview, buttons
