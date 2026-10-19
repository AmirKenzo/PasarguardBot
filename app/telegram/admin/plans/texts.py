"""Text templates for admin plans."""

PLAN_MENU_PROMPT = "یکی از گزینه‌های زیر را انتخاب کنید:"
NO_PLANS_TEXT = "هیچ پلنی موجود نیست."
PLAN_NOT_FOUND = "پلن یافت نشد!"
NUMBER_ONLY_ERROR = "📅 فقط مجاز به ارسال عدد هستید"
NO_PANEL_ERROR = "❌ پنلی وجود ندارد"
PANEL_NOT_SELECTED_ERROR = "❌ خطا: پنل انتخاب نشده است، لطفاً دوباره تلاش کنید."

PLAN_TYPE_LABELS = {
    "volume": "📊 حجمی",
    "unlimited_volume": "♾️ نامحدود حجمی",
    "fair_usage": "⚖️ مصرف منصفانه",
}

RESET_STRATEGY_LABELS = {
    "no_reset": "بدون ریست",
    "day": "روزانه",
    "week": "هفتگی",
    "month": "ماهانه",
    "year": "سالانه",
}

RESET_STRATEGY_ADD_LABELS = {
    "no_reset": "بدون ریست",
    "day": "ریست روزانه",
    "week": "ریست هفتگی",
    "month": "ریست ماهانه",
    "year": "ریست سالانه",
}


def to_persian_digits(text: str) -> str:
    persian_map = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
    return text.translate(persian_map)


def format_number(num):
    """English docstring for format_number."""
    if isinstance(num, int):
        return str(num)
    if isinstance(num, float):
        if num.is_integer():
            return str(int(num))
        return str(num)
    return str(num)


def ip_limit_text(ip_limit: int) -> str:
    return "♾️ نامحدود" if ip_limit == 0 else f"👥 {ip_limit} کاربر"
