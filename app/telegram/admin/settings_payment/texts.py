"""Text templates for admin settings_payment."""

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
CRYPTO_MIN_PROMPT = "حداقل مبلغ درگاه ارزی را وارد کنید:"
CRYPTO_MAX_PROMPT = "حداکثر مبلغ درگاه ارزی را وارد کنید:"
RESELLER_MIN_WALLET_PROMPT = "حداقل موجودی کیف پول برای خرید نمایندگی را وارد کنید (تومان):"
NUMERIC_ONLY = "لطفا فقط عدد ارسال کنید"
PERCENT_RANGE_ERROR = "درصد باید بین 0 تا 100 باشد"

MANUAL_LIMITS_SAVED = "✅ محدودیت کارت دستی ذخیره شد"
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

ADD_CARD_NUMBER_PROMPT = "شماره کارت جدید را ارسال کنید:"
SELECT_ACTIVE_CARD_PROMPT = "کارت مورد نظر را انتخاب کنید:"
NO_CARDS_REGISTERED = "هیچ کارتی ثبت نشده است."
ACTIVE_CARD_UPDATED = "کارت فعال بروزرسانی شد."
DELETE_CARD_PROMPT = "کارت مورد نظر را حذف کنید:"
CARD_DELETED = "کارت حذف شد."
SETTINGS_SAVED = "وضعیت جدید ذخیره شد"

MANUAL_BONUS_PERCENT_PROMPT = "درصد بونوس کارت دستی را وارد کنید (0-100):"
CRYPTO_BONUS_PERCENT_PROMPT = "درصد بونوس ارزی را وارد کنید (0-100):"

MANUAL_BONUS_SET_TEMPLATE = "✅ درصد بونوس کارت دستی روی {percent}% تنظیم شد\n\n{bonus_text}"
CRYPTO_BONUS_SET_TEMPLATE = "✅ درصد بونوس ارزی روی {percent}% تنظیم شد\n\n{bonus_text}"

MAAR_EDIT_VALUE_PROMPT = "مقدار جدید را بفرستید:"

TX_ALREADY_REVIEWED = "این تراکنش قبلا بررسی شده است"
TX_INVALID_AMOUNT = "❌ مبلغ نامعتبر است"
TX_INVALID_REQUEST = "❌ خطا در پردازش درخواست"

TX_APPROVED_ADMIN_HEADER = "✅ تراکنش تایید شد."
TX_REJECTED_ADMIN_HEADER = "❌ تراکنش رد شد."
TX_APPROVED_ADMIN_BUTTON = "🌟 تراکنش توسط ادمین تایید شده"
TX_REJECTED_ADMIN_BUTTON = "⛔️ تراکنش توسط ادمین رد شد ⛔️"

TX_APPROVED_USER_MESSAGE = (
    "✅ تراکنش کارت به کارت (دستی) شما تایید شد\n\n"
    "👤 شناسه شما: `{user_id}`\n"
    "💰 مبلغ `{amount}` تومان به حساب شما اضافه شد.\n"
    "{bonus_line}"
    "👜 موجودی شما به کیف پولتون در بات اضافه شده\n"
    "💳 اکنون می‌توانید از ربات خرید کنید."
)

TX_REJECT_USER_MESSAGE = (
    "#اطلاعیه\n"
    "🚫 کاربر گرامی تراکنش کارت به کارت شما توسط پشتیبانی رد شد.\n\n"
    "❕لطفا به مبلغی که وارد میکنید دقت کنید و حتما به هزارتومان تایپ کنید. برای مثال جهت تایید مبلغ 50,000 تومان باید عدد 50000 را به ربات ارسال کنید.\n\n"
    "⚠️ لطفا مراحلی که رفته بودید را یکبار چک کنید سپس دوباره از ابتدا سعی کنید تا بررسی شود."
)

TX_REJECTED_USER_MESSAGE = f"{TX_REJECT_USER_MESSAGE}\nمبلغ: `{{amount}}` تومان"

TX_RECEIPT_FIX_USER_MESSAGE = (
    "#اطلاعیه\n"
    "♻️ رسید شما برای بررسی دوباره نیاز به اصلاح مبلغ دارد.\n\n"
    "لطفا مبلغ را به تومان دوباره وارد کنید و سپس رسید را مجددا ارسال کنید.\n"
)

TX_CARD_MISMATCH_USER_MESSAGE = (
    "#اطلاعیه\n"
    "💳 شماره کارت واریزی شما با شماره کارت فعلی ربات تطابق ندارد.\n\n"
    "لطفا در دفعات بعد حتما به شماره کارت جدید واریز انجام دهید؛ در غیر این صورت تراکنش شما تایید نخواهد شد.\n"
)


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
        f"💵 **ارزی**: {settings.crypto_bonus_percent}% {'✅ فعال' if settings.crypto_bonus_enabled else '❌ غیرفعال'}\n\n"
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
