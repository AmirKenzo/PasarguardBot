"""Text templates for admin settings_payment."""

from app.utils.text.default_texts import DEFAULT_BOT_TEXTS

GATEWAY_SETTINGS_TRIGGER = "💳 تنظیمات درگاه"

CARD_HOLDER_NOT_SET = "تنظیم نشده"
CARD_NOT_REGISTERED = "ثبت نشده"

RANDOM_MODE_ACTIVE = "✅ فعال (کارت‌ها به صورت رندوم نمایش داده می‌شوند)"
RANDOM_MODE_INACTIVE = "❌ غیرفعال (کارت فعال نمایش داده می‌شود)"

MANUAL_CARD_VISIBILITY_ALL = "all"
MANUAL_CARD_VISIBILITY_SAFE_MODE = "safe_mode"

MANUAL_CARD_VISIBILITY_ALL_LABEL = "👥 تغییر به: نمایش برای همه"
MANUAL_CARD_VISIBILITY_SAFE_MODE_LABEL = "🛡 تغییر به: فقط سیف‌مود"

CARD_NAME_PROMPT = "نام دارنده کارت را ارسال کنید:"
CARD_ADDED_SUCCESS = "کارت جدید با موفقیت اضافه شد."
MANUAL_MIN_PROMPT = "حداقل مبلغ کارت دستی را وارد کنید:"
MANUAL_MAX_PROMPT = "حداکثر مبلغ کارت دستی را وارد کنید:"
AUTO_MIN_PROMPT = "حداقل مبلغ کارت خودکار را وارد کنید:"
AUTO_MAX_PROMPT = "حداکثر مبلغ کارت خودکار را وارد کنید:"
CRYPTO_MIN_PROMPT = "حداقل مبلغ درگاه ارزی را وارد کنید:"
CRYPTO_MAX_PROMPT = "حداکثر مبلغ درگاه ارزی را وارد کنید:"
RESELLER_MIN_WALLET_PROMPT = "حداقل موجودی کیف پول برای خرید نمایندگی را وارد کنید (تومان):"
NUMERIC_ONLY = "لطفا فقط عدد ارسال کنید"
PERCENT_RANGE_ERROR = "درصد باید بین 0 تا 100 باشد"

MANUAL_LIMITS_SAVED = "✅ محدودیت کارت دستی ذخیره شد"
AUTO_LIMITS_SAVED = "✅ محدودیت کارت خودکار ذخیره شد"
CRYPTO_LIMITS_SAVED = "✅ محدودیت درگاه ارزی ذخیره شد"
RESELLER_MIN_WALLET_SAVED = "✅ حداقل موجودی خرید نمایندگی ذخیره شد"

MAAR_ADD_MIN_PROMPT = "حداقل تراکنش موفق:"
MAAR_ADD_MAX_PROMPT = "حداکثر تراکنش موفق (عدد یا none):"
MAAR_ADD_DELAY_PROMPT = "زمان تایید (دقیقه، 0=دستی):"
MAAR_NUMERIC_OR_NONE = "عدد یا none"
MAAR_NUMERIC_ONLY = "فقط عدد"
MAAR_SAVED = "✅ ذخیره شد"
MAAR_NOT_FOUND = "یافت نشد"
MAAR_MANUAL_ONLY = "فقط دستی"

AUTO_CARD_NUMBER_SAVED_TEMPLATE = "✅ شماره کارت (خودکار) ثبت شد \n👤 شماره کارت: {card_number}"
AUTO_CARD_NAME_SAVED_TEMPLATE = "✅ نام کارت (خودکار) ثبت شد \n👤 نام کارت: {card_name}"
AUTO_CARD_NUMBER_CHANGE_PROMPT = "لطفا شماره کارت برای (تایید خودکار) تغییر ارسال کنید"
AUTO_CARD_NAME_CHANGE_PROMPT = "لطفا نام دارنده کارت برای (تایید خودکار) تغییر ارسال کنید"

ADD_CARD_NUMBER_PROMPT = "شماره کارت جدید را ارسال کنید:"
SELECT_ACTIVE_CARD_PROMPT = "کارت مورد نظر را انتخاب کنید:"
NO_CARDS_REGISTERED = "هیچ کارتی ثبت نشده است."
ACTIVE_CARD_UPDATED = "کارت فعال بروزرسانی شد."
DELETE_CARD_PROMPT = "کارت مورد نظر را حذف کنید:"
CARD_DELETED = "کارت حذف شد."
SETTINGS_SAVED = "وضعیت جدید ذخیره شد"

MANUAL_BONUS_PERCENT_PROMPT = "درصد بونوس کارت دستی را وارد کنید (0-100):"
AUTO_BONUS_PERCENT_PROMPT = "درصد بونوس کارت خودکار را وارد کنید (0-100):"
CRYPTO_BONUS_PERCENT_PROMPT = "درصد بونوس ارزی را وارد کنید (0-100):"
STARS_BONUS_PERCENT_PROMPT = "درصد بونوس استارز را وارد کنید (0-100):"

MANUAL_BONUS_SET_TEMPLATE = "✅ درصد بونوس کارت دستی روی {percent}% تنظیم شد\n\n{bonus_text}"
AUTO_BONUS_SET_TEMPLATE = "✅ درصد بونوس کارت خودکار روی {percent}% تنظیم شد\n\n{bonus_text}"
CRYPTO_BONUS_SET_TEMPLATE = "✅ درصد بونوس ارزی روی {percent}% تنظیم شد\n\n{bonus_text}"
STARS_BONUS_SET_TEMPLATE = "✅ درصد بونوس استارز روی {percent}% تنظیم شد\n\n{bonus_text}"

MAAR_EDIT_VALUE_PROMPT = "مقدار جدید را بفرستید:"

TX_ALREADY_REVIEWED = "این تراکنش قبلا بررسی شده است"
TX_INVALID_AMOUNT = "❌ مبلغ نامعتبر است"
TX_INVALID_REQUEST = "❌ خطا در پردازش درخواست"

TX_APPROVED_ADMIN_HEADER = "✅ تراکنش تایید شد."
TX_REJECTED_ADMIN_HEADER = "❌ تراکنش رد شد."
TX_APPROVED_ADMIN_BUTTON = "🌟 تراکنش توسط ادمین تایید شده"
TX_REJECTED_ADMIN_BUTTON = "⛔️ تراکنش توسط ادمین رد شد ⛔️"

TX_APPROVED_USER_MESSAGE = DEFAULT_BOT_TEXTS["manual_card_approved_message"]

TX_REJECT_USER_MESSAGE = (
    "#اطلاعیه\n"
    "🚫 کاربر گرامی تراکنش کارت به کارت شما توسط پشتیبانی رد شد.\n\n"
    "❕لطفا به مبلغی که وارد میکنید دقت کنید و حتما به هزارتومان تایپ کنید. برای مثال جهت تایید مبلغ 50,000 تومان باید عدد 50000 را به ربات ارسال کنید.\n\n"
    "⚠️ لطفا مراحلی که رفته بودید را یکبار چک کنید سپس دوباره از ابتدا سعی کنید تا بررسی شود."
)

TX_REJECTED_USER_MESSAGE = DEFAULT_BOT_TEXTS["manual_card_rejected_message"]

TX_RECEIPT_FIX_USER_MESSAGE = DEFAULT_BOT_TEXTS["manual_card_receipt_fix_message"]

TX_CARD_MISMATCH_USER_MESSAGE = DEFAULT_BOT_TEXTS["manual_card_card_mismatch_message"]


def manual_card_visibility_mode(settings) -> str:
    mode = getattr(settings, "manual_card_visibility", None) if settings else None
    if mode == MANUAL_CARD_VISIBILITY_SAFE_MODE:
        return MANUAL_CARD_VISIBILITY_SAFE_MODE
    return MANUAL_CARD_VISIBILITY_ALL


def next_manual_card_visibility_mode(settings) -> str:
    current = manual_card_visibility_mode(settings)
    if current == MANUAL_CARD_VISIBILITY_SAFE_MODE:
        return MANUAL_CARD_VISIBILITY_ALL
    return MANUAL_CARD_VISIBILITY_SAFE_MODE


def manual_card_visibility_button_label(settings) -> str:
    if manual_card_visibility_mode(settings) == MANUAL_CARD_VISIBILITY_SAFE_MODE:
        return MANUAL_CARD_VISIBILITY_ALL_LABEL
    return MANUAL_CARD_VISIBILITY_SAFE_MODE_LABEL


def manual_card_visibility_status(settings) -> str:
    if manual_card_visibility_mode(settings) == MANUAL_CARD_VISIBILITY_SAFE_MODE:
        return "فقط کاربران دارای سیف‌مود"
    return "همه کاربران"


def pay_mode_status(settings) -> str:
    if settings and settings.pay_mode:
        return "✅ فعال"
    return "❌ غیرفعال"


def is_manual_card_visible(settings, user) -> bool:
    if not settings or not settings.pay_mode:
        return False
    if manual_card_visibility_mode(settings) == MANUAL_CARD_VISIBILITY_SAFE_MODE:
        return user is not None and getattr(user, "safe_mode", None) is True
    return True


def auto_card_visibility_mode(settings) -> str:
    mode = getattr(settings, "auto_card_visibility", None) if settings else None
    if mode == MANUAL_CARD_VISIBILITY_ALL:
        return MANUAL_CARD_VISIBILITY_ALL
    return MANUAL_CARD_VISIBILITY_SAFE_MODE


def is_auto_card_visible(settings, user) -> bool:
    if not settings or not settings.auto_cart:
        return False
    if auto_card_visibility_mode(settings) == MANUAL_CARD_VISIBILITY_SAFE_MODE:
        return user is not None and bool(getattr(user, "safe", False))
    return True


def gateway_settings_message(manual_info: str, random_mode_status: str, settings) -> str:
    pay_mode_hint = ""
    if settings and not settings.pay_mode:
        pay_mode_hint = (
            "\n⚠️ **دکمه کارت دستی** در تنظیمات ربات خاموش است؛ "
            "برای نمایش در افزایش موجودی، از بخش «پرداخت‌ها» آن را فعال کنید.\n"
        )
    return (
        "💳 **کارت فعال برای کارت به کارت دستی**:\n"
        f"{manual_info}\n"
        f"🔘 **دکمه کارت دستی در ربات**: {pay_mode_status(settings)}\n"
        f"🎲 **حالت نمایش شماره کارت**: {random_mode_status}\n"
        f"👥 **نمایش دکمه کارت به کارت برای**: {manual_card_visibility_status(settings)}"
        f"{pay_mode_hint}\n\n"
        "برای تغییر هر گزینه، روی دکمه مربوطه بزنید."
    )


def gateway_settings_back_message(active, random_mode_status: str, settings) -> str:
    pay_mode_hint = ""
    if settings and not settings.pay_mode:
        pay_mode_hint = (
            "\n⚠️ **دکمه کارت دستی** در تنظیمات ربات خاموش است؛ "
            "برای نمایش در افزایش موجودی، از بخش «پرداخت‌ها» آن را فعال کنید.\n"
        )
    return (
        "💳 **شماره کارت ست شده برای کارت به کارت دستی**:\n"
        f"👤 **نام دارنده کارت**: `{active.name if (active and active.name) else CARD_HOLDER_NOT_SET}`\n"
        f"📄 **شماره کارت**:\n `{active.number if (active and active.number) else CARD_HOLDER_NOT_SET}`\n"
        f"🔘 **دکمه کارت دستی در ربات**: {pay_mode_status(settings)}\n"
        f"🎲 **حالت نمایش شماره کارت**: {random_mode_status}\n"
        f"👥 **نمایش دکمه کارت به کارت برای**: {manual_card_visibility_status(settings)}"
        f"{pay_mode_hint}\n\n"
        "برای تغییر هر گزینه، روی دکمه مربوطه بزنید."
    )


def manual_card_info(active) -> str:
    if active:
        return f"👤 **نام دارنده کارت**: `{active.name}`\n📄 **شماره کارت:** `{active.number}`"
    return CARD_NOT_REGISTERED


def bonus_settings_header(settings) -> str:
    return (
        "🎁 **تنظیمات بونوس درصدی**\n\n"
        f"💳 **کارت دستی**: {settings.manual_bonus_percent}% {'✅ فعال' if settings.manual_bonus_enabled else '❌ غیرفعال'}\n"
        f"💲 **کارت خودکار**: {settings.auto_bonus_percent}% {'✅ فعال' if settings.auto_bonus_enabled else '❌ غیرفعال'}\n"
        f"💵 **ارزی**: {settings.crypto_bonus_percent}% {'✅ فعال' if settings.crypto_bonus_enabled else '❌ غیرفعال'}\n"
        f"⭐ **استارز**: {settings.stars_bonus_percent}% {'✅ فعال' if settings.stars_bonus_enabled else '❌ غیرفعال'}\n\n"
        "روی گزینه‌های زیر کلیک کنید:"
    )


def maar_menu_header(master_status: str) -> str:
    return f"📋 **قوانین تایید خودکار**\n🔘 کلی: {master_status}\n"


MAAR_NO_RULES = "\nقانونی ثبت نشده."


def maar_range(rule) -> str:
    max_value = str(rule.max_successful_tx) if rule.max_successful_tx is not None else "∞"
    return f"{rule.min_successful_tx}–{max_value}"


def maar_delay(rule) -> str:
    return MAAR_MANUAL_ONLY if rule.auto_approve_delay_minutes <= 0 else f"{rule.auto_approve_delay_minutes} دقیقه"


def maar_rule_detail(rule_id: int, rule) -> str:
    max_value = str(rule.max_successful_tx) if rule.max_successful_tx is not None else "∞"
    return (
        f"قانون #{rule_id}\nحداقل: {rule.min_successful_tx}\nحداکثر: {max_value}\nزمان: {maar_delay(rule)}\n"
        f"وضعیت: {'فعال' if rule.is_active else 'غیرفعال'}"
    )


SMS_WEBHOOK_URL_MISSING = (
    "⚠️ `WEBAPP_URL` در فایل `.env` تنظیم نشده؛ آدرس را دستی بسازید:\n`https://<دامنه-ربات>/api/sms`"
)
SMS_WEBHOOK_KEY_MISSING = "⚠️ کلید ساخته نشده؛ «ساخت کلید جدید» را بزنید."
SMS_WEBHOOK_ROTATE_CONFIRM = (
    "🔄 **ساخت کلید جدید وبهوک پیامک**\n\n"
    "با این کار کلید فعلی **همین الان باطل می‌شود** و تا کلید جدید را در اپ گوشی وارد نکنید، "
    "هیچ واریزی خودکار تایید نمی‌شود.\n\n"
    "فقط وقتی این کار را بکنید که کلید لو رفته یا می‌خواهید گوشی قبلی را قطع کنید. ادامه می‌دهید؟"
)
SMS_WEBHOOK_ROTATED_NOTE = "✅ کلید جدید ساخته شد و کلید قبلی باطل شد. همین الان آن را در اپ گوشی جایگزین کنید."
SMS_WEBHOOK_ROTATE_FAILED = "❌ ساخت کلید جدید ناموفق بود؛ کلید قبلی هنوز فعال است."


def _sms_url_line(url: str | None) -> str:
    return f"`{url}`" if url else SMS_WEBHOOK_URL_MISSING


def _sms_key_line(key: str) -> str:
    return f"`{key}`" if key else SMS_WEBHOOK_KEY_MISSING


def sms_webhook_message(url: str | None, key_display: str, note: str | None = None) -> str:
    head = f"{note}\n\n" if note else ""
    return (
        f"{head}"
        "📲 **وبهوک پیامک (کارت‌به‌کارت خودکار)**\n\n"
        "یک اپ روی گوشیِ دارای سیم‌کارت حساب، پیامک واریز بانک را به این آدرس می‌فرستد "
        "و ربات فاکتور هم‌مبلغ را خودکار تایید می‌کند.\n\n"
        f"🌐 **آدرس وبهوک**:\n{_sms_url_line(url)}\n\n"
        f"🔑 **کلید API**:\n{_sms_key_line(key_display)}\n\n"
        "📱 اپ‌های پشتیبانی‌شده: **ForApp** (پیشنهادی) و **SmsForwarder**؛ "
        "راهنمای هرکدام را از دکمه‌های زیر ببینید.\n\n"
        "⚠️ کلید را به کسی ندهید؛ هرکس آن را داشته باشد می‌تواند واریز جعلی ثبت کند. "
        "اگر لو رفت، «ساخت کلید جدید» را بزنید."
    )


def sms_webhook_forapp_guide(url: str | None, key: str) -> str:
    return (
        "📘 **راهنمای ForApp**\n\n"
        "1️⃣ ForApp را از `github.com/erfjab/forapp/releases` روی گوشیِ دارای سیم‌کارت حساب نصب کنید "
        "و دسترسی پیامک و «بدون محدودیت باتری» را بدهید.\n\n"
        "2️⃣ در بخش **بانک‌ها** شماره‌ی فرستنده‌ی پیامک بانکتان را اضافه کنید "
        "(فقط پیامک همین شماره‌ها فرستاده می‌شود).\n\n"
        "3️⃣ یک **مقصد** از نوع وبهوک بسازید:\n"
        f"• آدرس: {_sms_url_line(url)}\n"
        "• روش: `POST` و نوع بدنه: `JSON`\n"
        "• قالب بدنه و هدرها: **پیش‌فرض را دست نزنید**\n"
        f"• کلید API: {_sms_key_line(key)}\n\n"
        "4️⃣ «ارسال آزمایشی» را بزنید؛ باید موفق شود. پیام آزمایشی هیچ فاکتوری را تایید نمی‌کند.\n\n"
        "5️⃣ پیشنهاد: گزینه‌ی «فقط واریزها» را روشن کنید.\n\n"
        "💡 اگر کلید اشتباه باشد، ForApp خطای `401` نشان می‌دهد. "
        "اگر بانکتان در ربات قالب نداشته باشد، مبلغی که ForApp تشخیص داده استفاده می‌شود."
    )


def sms_webhook_smsforwarder_guide(url: str | None, key: str) -> str:
    return (
        "📘 **راهنمای SmsForwarder**\n\n"
        "1️⃣ در بخش **ارسال‌کننده‌ها (Sender)** یکی از نوع **Webhook** بسازید:\n"
        f"• آدرس: {_sms_url_line(url)}\n"
        "• روش: `POST`\n"
        f"• هدر: `X-API-Key` با مقدار {_sms_key_line(key)}\n"
        "• هدر: `Content-Type` با مقدار `application/json`\n"
        "• قالب پارامترها (webParams):\n"
        '`{"text":"[org_content]","from":"[from]","timestamp":"[timestamp]"}`\n\n'
        "2️⃣ در بخش **قوانین (Rule)** یک قانون پیامک بسازید که شماره‌ی فرستنده‌ی بانک را "
        "به همین ارسال‌کننده وصل کند.\n\n"
        "3️⃣ با یک واریز کوچک تست کنید و نتیجه را در لاگ اپ ببینید.\n\n"
        "💡 SmsForwarder مبلغ را جدا نمی‌فرستد؛ پس فقط بانک‌هایی کار می‌کنند که قالبشان در ربات تعریف شده. "
        "پیامک واریزی که خوانده نشود با هشتگ `#sms_unparsed` در کانال لاگ می‌آید."
    )


def mask_secret(value: str | None) -> str:
    key = (value or "").strip()
    if len(key) <= 8:
        return "***" if key else ""
    return f"{key[:4]}…{key[-4:]}"


def auto_card_menu_message(settings, webhook_url: str | None) -> str:
    status = "✅ روشن" if settings.auto_cart else "❌ خاموش"
    audience = (
        "فقط کاربران دارای سیف‌مود"
        if auto_card_visibility_mode(settings) == MANUAL_CARD_VISIBILITY_SAFE_MODE
        else "همه کاربران"
    )
    return (
        "🤖 **کارت به کارت خودکار**\n\n"
        f"🔘 **وضعیت**: {status}\n"
        f"👥 **نمایش دکمه برای**: {audience}\n\n"
        f"👤 **نام دارنده کارت**: `{settings.cart_name or CARD_HOLDER_NOT_SET}`\n"
        f"📄 **شماره کارت**: `{settings.cart_num or CARD_HOLDER_NOT_SET}`\n\n"
        f"💰 **محدودیت مبلغ**: `{int(settings.auto_deposit_min or 0):,}` تا "
        f"`{int(settings.auto_deposit_max or 0):,}` تومان\n\n"
        f"📲 **وبهوک پیامک**: {_sms_url_line(webhook_url)}"
    )
