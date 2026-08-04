"""Text templates for slim business admin commands."""

ADMIN_HELP_TEXT = """🔐 **دستورات ادمین**

📋 دستورات موجود:
• `add <amount>` or `+ <amount>` - افزایش موجودی کاربر فعلی
• `add <user_id> <amount>` - افزایش موجودی کاربر
• `remove <amount>` or `- <amount>` - کاهش موجودی کاربر فعلی
• `remove <user_id> <amount>` - کاهش موجودی کاربر
• `info` - نمایش اطلاعات کاربر فعلی
• `info <user_id>` - نمایش اطلاعات کاربر
• `id` - نمایش آیدی کاربر فعلی چت
• `ip <ip_or_domain>` or `ping <ip_or_domain>` - بررسی IP/دامنه و پینگ

example:
• `add 10000` or `+ 10000`
• `add 1919779290 10000`
• `remove 5000` or `- 5000`
• `remove 1919779290 5000`
• `info`
• `info 1919779290`
• `id`
• `ip 8.8.8.8` or `ping google.com`"""

ADD_FORMAT_ERROR = (
    "❌ **خطا**\n\nفرمت صحیح: `add <amount>` یا `add <user_id> <amount>`\nمثال: `add 10000` یا `add 1919779290 10000`"
)
ADD_NUMERIC_ERROR = "❌ **خطا**\n\nلطفاً مبلغ را به صورت عدد وارد کنید.\nمثال: `add 10000` یا `add 1919779290 10000`"
REMOVE_FORMAT_ERROR = (
    "❌ **خطا**\n\nفرمت صحیح: `remove <amount>` یا `remove <user_id> <amount>`\n"
    "مثال: `remove 5000` یا `remove 1919779290 5000`"
)
REMOVE_NUMERIC_ERROR = (
    "❌ **خطا**\n\nلطفاً مبلغ را به صورت عدد وارد کنید.\nمثال: `remove 5000` یا `remove 1919779290 5000`"
)
INFO_ID_ERROR = "❌ **خطا**\n\nلطفاً شناسه کاربر را به صورت عدد وارد کنید.\nمثال: `info` یا `info 1919779290`"
IP_EMPTY_ERROR = "❌ **خطا**\n\nلطفاً IP یا دامنه را وارد کنید.\nمثال: `ip 8.8.8.8` یا `ip google.com`"
IP_INVALID_ERROR = "❌ **خطا**\n\nفرمت IP یا دامنه نامعتبر است!\n\nمثال:\n• `ip 8.8.8.8`\n• `ip google.com`"
IP_NOT_FOUND = "❌ **خطا**\n\nاطلاعاتی برای این IP/دامنه یافت نشد!"
USER_NOT_FOUND_ERROR = "❌ **خطا**\n\nکاربری با شناسه `{user_id}` پیدا نشد!"


def user_id_text(user_id: int) -> str:
    return f"**UserID:** `{user_id}`"


def balance_added_text(*, user_id: int, old_balance: int, amount: int, new_balance: int) -> str:
    return (
        f"✅ **موجودی با موفقیت افزایش یافت**\n\n"
        f"👤 شناسه کاربر: `{user_id}`\n"
        f"💰 موجودی قبلی: `{old_balance:,}` تومان\n"
        f"➕ مبلغ افزوده شده: `{amount:,}` تومان\n"
        f"💰 موجودی جدید: `{new_balance:,}` تومان"
    )


def balance_removed_text(*, user_id: int, old_balance: int, amount: int, new_balance: int) -> str:
    return (
        f"✅ **موجودی با موفقیت کاهش یافت**\n\n"
        f"👤 شناسه کاربر: `{user_id}`\n"
        f"💰 موجودی قبلی: `{old_balance:,}` تومان\n"
        f"➖ مبلغ کسر شده: `{amount:,}` تومان\n"
        f"💰 موجودی جدید: `{new_balance:,}` تومان"
    )


def insufficient_balance_text(*, old_balance: int, amount: int) -> str:
    return (
        f"❌ **خطا**\n\nموجودی کاربر کافی نیست!\n"
        f"💰 موجودی فعلی: `{old_balance:,}` تومان\n"
        f"➖ مبلغ درخواستی: `{amount:,}` تومان"
    )


def generic_error_text(error: str) -> str:
    return f"❌ **خطا**\n\n{error}"
