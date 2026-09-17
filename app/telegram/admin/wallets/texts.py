"""Text templates for admin wallets."""

WALLETS_MENU_EMPTY = "💼 **مدیریت کیف پول‌ها**\n\nهیچ کیف پولی ثبت نشده است.\n\nروی گزینه‌های زیر کلیک کنید:"
WALLETS_MENU_HEADER = "💼 **مدیریت کیف پول‌ها**\n\n"
WALLETS_MENU_FOOTER = "روی گزینه‌های زیر کلیک کنید:"
WALLET_API_CONFIGURED = "✅ تنظیم شده"
WALLET_API_NOT_CONFIGURED = "❌ تنظیم نشده"

WALLET_TYPE_NOT_FOUND_ERROR = "❌ خطا: نوع کیف پول یافت نشد. لطفاً دوباره تلاش کنید."
WALLET_INFO_ERROR = "❌ خطا در دریافت اطلاعات. لطفاً دوباره تلاش کنید."

# Where to get the explorer/node API key for each wallet type, and whether
# automatic on-chain confirmation actually needs it (vs. being optional).
WALLET_API_KEY_SOURCES: dict[str, tuple[str, str]] = {
    "TRX": ("TronScan", "https://tronscan.org/#/myaccount/apiKeys"),
    "USDT": ("TronScan", "https://tronscan.org/#/myaccount/apiKeys"),
    "TON": ("TonConsole (TonAPI)", "https://tonconsole.com/"),
    "USDT-TON": ("TonConsole (TonAPI)", "https://tonconsole.com/"),
    "USDT-BEP20": ("MegaNode / NodeReal", "https://nodereal.io/meganode"),
    "POL": ("Alchemy (Polygon)", "https://dashboard.alchemy.com/"),
}
WALLET_API_KEY_REQUIRED_TYPES = frozenset({"USDT-BEP20", "POL"})
WALLET_ADDRESS_PROMPT_TEMPLATE = "آدرس کیف پول {wallet_type} را ارسال کنید:"
WALLET_DUPLICATE_ERROR_TEMPLATE = "❌ کیف پول {wallet_type} قبلاً اضافه شده است. نمی‌توانید کیف پول تکراری اضافه کنید."
WALLET_ADDED_SUCCESS_TEMPLATE = "✅ کیف پول {wallet_type} با موفقیت اضافه شد."
WALLET_ADD_FAILED = "❌ خطا در افزودن کیف پول. لطفاً دوباره تلاش کنید."
WALLET_TYPE_SELECT_PROMPT_TEMPLATE = "نوع کیف پول را انتخاب کنید (فعلی: {current_type}):"
WALLET_TYPE_CHANGE_BLOCKED_TEMPLATE = "❌ کیف پول {wallet_type} قبلاً اضافه شده است. نمی‌توانید به این نوع تغییر دهید."
WALLET_UPDATED_SUCCESS_TEMPLATE = "✅ کیف پول {wallet_type} با موفقیت بروزرسانی شد."
WALLET_UPDATE_FAILED = "❌ خطا در بروزرسانی کیف پول. لطفاً دوباره تلاش کنید."
WALLET_DELETED_SUCCESS = "✅ کیف پول با موفقیت حذف شد."
WALLET_DELETE_FAILED = "❌ خطا در حذف کیف پول. لطفاً دوباره تلاش کنید."
WALLET_NOT_FOUND = "❌ کیف پول یافت نشد."
WALLET_LIST_EMPTY = "هیچ کیف پولی ثبت نشده است."
WALLET_LIST_HEADER = "📋 **لیست کیف پول‌ها**\n\n"
WALLET_ALL_TYPES_EXIST = "❌ همه نوع کیف پول‌ها (TRX, USDT, USDT-TON, USDT-BEP20, TON, POL) قبلاً اضافه شده‌اند."
WALLET_TYPE_SELECT_PROMPT = "نوع کیف پول را انتخاب کنید:"
WALLET_EDIT_SELECT_PROMPT = "کیف پول مورد نظر را برای ویرایش انتخاب کنید:"
WALLET_DELETE_SELECT_PROMPT = "کیف پول مورد نظر را برای حذف انتخاب کنید:"
WALLET_DELETED_INLINE_TEMPLATE = "✅ کیف پول {wallet_type} با موفقیت حذف شد.\n\n"

ADD_BALANCE_USER_ID_PROMPT = "〰️ لطفا آیدی عددی کاربر را ارسال کنید:"
ADD_BALANCE_AMOUNT_PROMPT = "〰️ مبلع رو ارسال کنید"
DEDUCT_BALANCE_AMOUNT_PROMPT = "〰️ مبلع رو ارسال کنید برای کسر موجودی"

GROUP_CHARGE_MENU_TEXT = (
    "💰 **شارژ گروهی**\n\n"
    "🔹 این قابلیت مبلغ مشخصی را به موجودی تمام کاربران یا کاربران دارای سرویس فعال اضافه می‌کند.\n\n"
    "🔹 لطفا نوع کاربران را انتخاب کنید:"
)

GROUP_RESET_MENU_TEXT = (
    "🔄 **ریست دریافت تست**\n\n"
    "🔹 این قابلیت فیلد `tested` کاربرانی که تست گرفته‌اند را از 1 به 0 تبدیل می‌کند تا بتوانند دوباره تست دریافت کنند.\n\n"
    "🔹 لطفا نوع کاربران را انتخاب کنید:"
)

GROUP_CHARGE_INVALID_NUMBER = "⚠️ **خطا در ورودی**\n\nلطفا فقط عدد وارد کنید.\nمثال: 10000"
GROUP_CHARGE_INVALID_AMOUNT = "⚠️ **خطا در مبلغ**\n\nمبلغ باید بیشتر از صفر باشد.\nلطفا یک مبلغ معتبر وارد کنید."
GROUP_CHARGE_CANCELLED = "❌ **شارژ گروهی لغو شد**"
GROUP_RESET_CANCELLED = "❌ **ریست دریافت تست لغو شد**"
GROUP_CHARGE_NO_USERS = "❌ **شارژ گروهی**\n\nهیچ کاربری یافت نشد."

ALL_USERS_LABEL = "تمام کاربرها"
ACTIVE_SERVICE_USERS_LABEL = "کاربرهای دارای سرویس فعال"


def wallet_api_key_prompt(wallet_type: str | None = None, *, api_key_status: str | None = None) -> str:
    kind = (wallet_type or "").upper()
    required = kind in WALLET_API_KEY_REQUIRED_TYPES
    source = WALLET_API_KEY_SOURCES.get(kind)

    skip_hint = "API Key را ارسال کنید:" if required else "API Key را ارسال کنید یا برای رد شدن /skip بفرستید."
    if source:
        provider, url = source
        required_note = f"\n\nبرای تایید خودکار {kind} این کلید لازم است." if required else ""
        text = f"🔑 API Key برای {kind}{required_note}\n\nکلید را از **{provider}** بگیرید:\n{url}\n\n{skip_hint}"
    else:
        text = f"🔑 API Key برای {kind}\n\n{skip_hint}" if kind else f"🔑 API Key\n\n{skip_hint}"

    if api_key_status is not None:
        text += f"\n\nوضعیت فعلی: {api_key_status}"
    return text


def wallet_menu_line(wallet) -> str:
    return (
        f"**{wallet.type}**\n"
        f"📍 آدرس: `{wallet.address[:20]}...`\n"
        f"🔑 API Key: {WALLET_API_CONFIGURED if wallet.api_key else WALLET_API_NOT_CONFIGURED}\n\n"
    )


def wallet_list_entry(wallet) -> str:
    return (
        f"**{wallet.type}** (ID: {wallet.id})\n"
        f"📍 آدرس: `{wallet.address}`\n"
        f"🔑 API Key: {'✅' if wallet.api_key else '❌'}\n\n"
    )


def wallet_edit_text(wallet) -> str:
    return (
        f"**ویرایش کیف پول {wallet.type}**\n\n"
        f"📍 آدرس فعلی: `{wallet.address}`\n"
        f"🔑 API Key: {WALLET_API_CONFIGURED if wallet.api_key else WALLET_API_NOT_CONFIGURED}\n\n"
        "آدرس جدید را ارسال کنید:"
    )


def balance_added_admin_message(username, amount: int, new_amount) -> str:
    return (
        f"💳 حساب کاربر با موفقیت شارژ شد\n\n"
        f"🔹 شناسه کاربری: `{username}`\n"
        f"🔹 مبلغ واریز شده: `{amount:,}` تومان\n\n"
        f"💰 موجودی جدید: `{int(new_amount):,}` تومان"
    )


def balance_added_user_message(username, amount: int, new_amount) -> str:
    return (
        f"✅ کاربر گرامی، با شناسه `{username}`\n"
        f"مبلغ `{amount:,}` تومان توسط ادمین به حساب شما اضافه شد.\n\n"
        f"💰 موجودی جدید شما: `{int(new_amount):,}` تومان"
    )


def balance_deducted_admin_message(username, amount: int, new_amount) -> str:
    return (
        f"💳 حساب کاربر با موفقیت کسر شد\n\n"
        f"🔹 شناسه کاربری: `{username}`\n"
        f"🔹 مبلغ کسر شده: `{amount:,}` تومان\n\n"
        f"💰 موجودی جدید: `{int(new_amount):,}` تومان"
    )


def balance_deducted_user_message(username, amount: int, new_amount) -> str:
    return (
        f"❌ کاربر گرامی، با شناسه `{username}`\n"
        f"مبلغ `{amount:,}` تومان توسط ادمین از حساب شما کسر شد.\n\n"
        f"💰 موجودی جدید شما: `{int(new_amount):,}` تومان"
    )


def group_charge_confirmation(user_type_text: str, amount: int) -> str:
    return (
        f"⚠️ **تایید شارژ گروهی**\n\n"
        f"📋 **توضیحات:**\n"
        f"این عملیات مبلغ مشخص شده را به موجودی کاربران انتخاب شده اضافه می‌کند.\n\n"
        f"📊 **جزئیات:**\n"
        f"🔹 نوع کاربران: {user_type_text}\n"
        f"💰 مبلغ هر نفر: `{amount:,}` تومان\n\n"
        f"❓ آیا مطمئن هستید؟"
    )


def group_charge_amount_prompt(user_type_text: str) -> str:
    return (
        f"💰 **شارژ گروهی**\n\n"
        f"🔹 نوع کاربران انتخاب شده: {user_type_text}\n\n"
        f"〰️ لطفا مبلغ را به تومان وارد کنید:\n"
        f"(مثال: 10000 برای ده هزار تومان)"
    )


def group_charge_processing(user_type_text: str, user_count: int, amount: int) -> str:
    return (
        f"⏳ **در حال پردازش شارژ گروهی...**\n\n"
        f"🔹 نوع کاربران: {user_type_text}\n"
        f"👥 تعداد کاربران: {user_count} نفر\n"
        f"💰 مبلغ هر نفر: `{amount:,}` تومان\n"
        f"📝 در حال اضافه کردن موجودی..."
    )


def group_charge_result(
    user_type_text: str, total_users: int, success_count: int, failed_count: int, amount: int, total_charged: int
) -> str:
    return (
        f"✅ **شارژ گروهی با موفقیت انجام شد**\n\n"
        f"📋 **نتیجه عملیات:**\n"
        f"🔹 نوع کاربران: {user_type_text}\n"
        f"👥 تعداد کل: {total_users} نفر\n"
        f"✅ موفق: {success_count} نفر\n"
        f"❌ ناموفق: {failed_count} نفر\n\n"
        f"💰 **جزئیات مالی:**\n"
        f"💰 مبلغ هر نفر: `{amount:,}` تومان\n"
        f"💰 کل مبلغ شارژ شده: `{total_charged:,}` تومان"
    )


def group_charge_log_message(
    admin_id,
    user_type_text: str,
    user_count: int,
    success_count: int,
    failed_count: int,
    amount: int,
    total_charged: int,
) -> str:
    return (
        f"💰 **شارژ گروهی**\n\n"
        f"👤 ادمین: `{admin_id}`\n"
        f"📋 عملیات: اضافه کردن موجودی به کاربران\n"
        f"🔹 نوع کاربران: {user_type_text}\n"
        f"👥 تعداد کاربران: {user_count}\n"
        f"✅ موفق: {success_count}\n"
        f"❌ ناموفق: {failed_count}\n"
        f"💰 مبلغ هر نفر: `{amount:,}` تومان\n"
        f"💰 کل مبلغ: `{total_charged:,}` تومان"
    )


def group_charge_users_error(error_text: str) -> str:
    return f"❌ **شارژ گروهی**\n\nخطا در دریافت لیست کاربران:\n`{error_text}`"


NO_TESTED_USERS = "❌ **ریست دریافت تست**\n\nهیچ کاربری که تست گرفته باشد یافت نشد.\n\n(کاربرانی که فیلد `tested` آن‌ها برابر با 1 است)"

NO_TESTED_ACTIVE_USERS = "❌ **ریست دریافت تست**\n\nهیچ کاربری که تست گرفته باشد و سرویس فعال داشته باشد یافت نشد.\n\n(کاربرانی که فیلد `tested` آن‌ها برابر با 1 است و سرویس فعال دارند)"


def group_reset_confirmation(user_type_text: str, tested_count: int, reset_count: int) -> str:
    return (
        f"⚠️ **تایید ریست دریافت تست**\n\n"
        f"📋 **توضیحات:**\n"
        f"این عملیات فیلد `tested` کاربرانی که تست گرفته‌اند را از 1 به 0 تبدیل می‌کند.\n"
        f"پس از ریست، این کاربران می‌توانند دوباره تست (کانفیگ رایگان) دریافت کنند.\n\n"
        f"📊 **آمار:**\n"
        f"🔹 نوع کاربران: {user_type_text}\n"
        f"👥 تعداد کل کاربرانی که تست گرفته‌اند: {tested_count} نفر\n"
        f"🔄 تعداد کاربرانی که ریست می‌شوند: {reset_count} نفر\n\n"
        f"❓ آیا مطمئن هستید؟"
    )


def group_reset_processing(user_type_text: str, tested_count: int, reset_count: int) -> str:
    return (
        f"⏳ **در حال پردازش ریست دریافت تست...**\n\n"
        f"🔹 نوع کاربران: {user_type_text}\n"
        f"👥 تعداد کل کاربرانی که تست گرفته‌اند: {tested_count} نفر\n"
        f"🔄 تعداد کاربرانی که ریست می‌شوند: {reset_count} نفر\n"
        f"📝 در حال تبدیل فیلد `tested` از 1 به 0..."
    )


def group_reset_result(
    user_type_text: str, tested_count: int, reset_count: int, success_count: int, failed_count: int
) -> str:
    return (
        f"✅ **ریست دریافت تست با موفقیت انجام شد**\n\n"
        f"📋 **نتیجه عملیات:**\n"
        f"🔹 نوع کاربران: {user_type_text}\n"
        f"👥 تعداد کل کاربرانی که تست گرفته‌اند: {tested_count} نفر\n"
        f"🔄 تعداد کاربرانی که ریست شدند: {reset_count} نفر\n"
        f"✅ موفق: {success_count} نفر\n"
        f"❌ ناموفق: {failed_count} نفر\n\n"
        f"✨ **نتیجه:**\n"
        f"فیلد `tested` کاربران موفق از 1 به 0 تبدیل شد.\n"
        f"این کاربران اکنون می‌توانند دوباره تست (کانفیگ رایگان) دریافت کنند."
    )


def group_reset_log_message(
    admin_id, user_type_text: str, tested_count: int, reset_count: int, success_count: int, failed_count: int
) -> str:
    return (
        f"🔄 **ریست دریافت تست**\n\n"
        f"👤 ادمین: `{admin_id}`\n"
        f"📋 عملیات: ریست فیلد `tested` از 1 به 0\n"
        f"🔹 نوع کاربران: {user_type_text}\n"
        f"👥 تعداد کل کاربرانی که تست گرفته‌اند: {tested_count}\n"
        f"🔄 تعداد کاربرانی که ریست شدند: {reset_count}\n"
        f"✅ موفق: {success_count}\n"
        f"❌ ناموفق: {failed_count}"
    )


def group_reset_users_error(error_text: str) -> str:
    return f"❌ خطا در دریافت لیست کاربران: {error_text}"
