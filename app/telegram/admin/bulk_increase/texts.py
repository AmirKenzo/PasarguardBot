"""Text templates for admin bulk_increase."""

from datetime import datetime
from typing import Any

from app.telegram.admin.bulk_increase import states
from app.utils.formatting.traffic import format_size

NO_PANELS_ERROR = "❌ هیچ پنلی یافت نشد."
PANEL_SELECT_PROMPT = (
    "📈 **افزایش/کسر حجم و زمان همگانی**\n\n"
    "🔹 این قابلیت حجم و/یا زمان را برای تمام سرویس‌های یک پنل یا همه پنل‌ها اضافه یا کسر می‌کند.\n\n"
    "🔹 لطفا پنل مورد نظر را انتخاب کنید:"
)
VOLUME_INPUT_ERROR = "⚠️ **خطا در ورودی**\n\nلطفا فقط عدد وارد کنید.\nمثال: 5 یا -5"
VOLUME_ZERO_ERROR = "⚠️ **خطا در حجم**\n\nحجم نباید صفر باشد. برای کسر حجم عدد منفی وارد کنید."
TIME_INPUT_ERROR = "⚠️ **خطا در ورودی**\n\nلطفا عدد صحیح روز وارد کنید.\nمثال: 7 یا -7"
TIME_ZERO_ERROR = "⚠️ **خطا در زمان**\n\nزمان نباید صفر باشد. برای کسر زمان عدد منفی وارد کنید."
VOLUME_SET_PROMPT = (
    "📊 **تنظیم حجم**\n\n"
    "〰️ حجم را به گیگابایت وارد کنید.\n"
    "برای افزودن عدد مثبت و برای کسر عدد منفی بفرستید.\n"
    "(مثال: 5 یا -5)"
)
TIME_SET_PROMPT = (
    "⏰ **تنظیم زمان**\n\n"
    "〰️ زمان را به روز و عدد صحیح وارد کنید.\n"
    "برای افزودن عدد مثبت و برای کسر عدد منفی بفرستید.\n"
    "(مثال: 7 یا -7)"
)
CANCELLED_TEXT = "❌ **تغییر حجم و زمان همگانی لغو شد**"
MIN_SETTING_REQUIRED_ALERT = "❌ لطفا حداقل حجم یا زمان را تنظیم کنید."
PREFLIGHT_CHECKING_TEXT = (
    "🔎 **در حال بررسی دسترسی bulk پاسارگارد...**\n\n"
    "🔹 {panel_text}\n"
    "📊 حجم: {volume_text}\n"
    "⏰ زمان: {time_text}\n"
    "📝 لطفا صبر کنید..."
)
NOT_SET = "تنظیم نشده"
UNCHANGED = "تغییر نمی‌کند"
NO_CHANGE = "بدون تغییر"


def _format_amount(value: float | int) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return f"{value:g}"


def shorten(text: str, limit: int = 220) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def remember_issue(issues: list[str], text: str) -> None:
    issues.append(shorten(text))
    del issues[: -states.MAX_ERROR_DETAILS]


def timestamp_or_none(value: Any) -> int | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return int(value.timestamp())
    if isinstance(value, (int, float)):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def signed_action_text(value: float | int, unit: str) -> str:
    if value > 0:
        return f"افزودن {_format_amount(value)} {unit}"
    if value < 0:
        return f"کسر {_format_amount(abs(value))} {unit}"
    return UNCHANGED


def format_signed_size_delta(value: int) -> str:
    if value > 0:
        return f"افزودن {format_size(value, decimal_places=2)}"
    if value < 0:
        return f"کسر {format_size(abs(value), decimal_places=2)}"
    return NO_CHANGE


def format_signed_days_delta(value: int) -> str:
    if value > 0:
        return f"افزودن {value} روز"
    if value < 0:
        return f"کسر {abs(value)} روز"
    return NO_CHANGE


def parse_day_amount(raw: str) -> int | None:
    value = raw.strip()
    if not value:
        return None
    unsigned = value[1:] if value[0] in "+-" else value
    if not unsigned.isdigit():
        return None
    return int(value)


def operation_texts(volume: str | None, time_days: str | None) -> tuple[str, str]:
    volume_text = signed_action_text(float(volume), "گیگابایت") if volume else UNCHANGED
    time_text = signed_action_text(int(time_days), "روز") if time_days else UNCHANGED
    return volume_text, time_text


def panel_text_from_code(panel_code_str: str | None) -> str:
    return "همه پنل‌ها" if panel_code_str == "all" else f"پنل: {panel_code_str}"


def panel_scope_text(panel_code_str: str | None, panel_count: int) -> str:
    if panel_code_str == "all":
        return f"{panel_count} پنل"
    return f"پنل: {panel_code_str}"


def settings_menu_text(panel_code_str: str | None, volume_text: str, time_text: str) -> str:
    panel_text = panel_text_from_code(panel_code_str)
    return (
        f"📈 **افزایش/کسر حجم و زمان همگانی**\n\n"
        f"🔹 {panel_text}\n\n"
        f"📋 **تنظیمات:**\n"
        f"📊 حجم: {volume_text}\n"
        f"⏰ زمان: {time_text}\n\n"
        f"🔹 لطفا حجم و/یا زمان را تنظیم کنید:"
    )


def initial_settings_menu_text(panel_code_str: str | None) -> str:
    return settings_menu_text(panel_code_str, NOT_SET, NOT_SET)


def panel_label(panel) -> str:
    return panel.name or f"پنل {panel.code}"


def build_preflight_message(
    panels: list,
    jobs: list[dict],
    strategies: dict[int, dict],
    volume_text: str,
    time_text: str,
    panel_text: str,
    *,
    job_valid_count,
) -> str:
    total_services = sum(len(job["services"]) for job in jobs)
    target_services = sum(
        job_valid_count(job, bulk=bool(strategies.get(job["panel"].code, {}).get("can_bulk"))) for job in jobs
    )
    skipped_services = total_services - target_services
    bulk_panels = sum(1 for strategy in strategies.values() if strategy["can_bulk"])
    manual_panels = len(panels) - bulk_panels

    if bulk_panels == len(panels):
        mode_text = "همه پنل‌ها با bulk پاسارگارد انجام می‌شوند و عملیات سریع تکمیل می‌شود."
    elif bulk_panels:
        mode_text = f"{bulk_panels} پنل با bulk و {manual_panels} پنل به‌صورت معمولی انجام می‌شود."
    else:
        mode_text = "دسترسی کافی برای bulk پیدا نشد؛ عملیات به‌صورت معمولی و تک‌به‌تک انجام می‌شود."

    lines = [
        "📈 **پیش‌بررسی تغییر همگانی**",
        "",
        f"🔹 محدوده: {panel_text}",
        f"📊 حجم: {volume_text}",
        f"⏰ زمان: {time_text}",
        f"🔄 سرویس‌های فعال قابل اعمال: {target_services}",
        f"⚠️ سرویس‌های ردشده به‌خاطر username/panel_userid ناقص: {skipped_services}",
        "",
        f"🚀 **روش اجرا:** {mode_text}",
    ]

    if manual_panels:
        lines.extend(
            [
                "",
                "برای استفاده از bulk در پنل پاسارگارد باید این دسترسی‌ها فعال باشند:",
                "users.update = all",
                "admins.read_simple = true",
                "در غیر اینصورت برای هر سرویس جداگانه به پنل درخواست زده می‌شود و در تعداد بالا زمان‌بر است.",
            ]
        )

    lines.append("")
    lines.append("📋 **وضعیت پنل‌ها:**")
    for job in jobs[:10]:
        panel = job["panel"]
        strategy = strategies.get(panel.code, {})
        mode = "bulk" if strategy.get("can_bulk") else "معمولی"
        reason = shorten(strategy.get("reason", "نامشخص"), 160)
        lines.append(f"• {panel_label(panel)}: {mode} - {reason}")
    if len(jobs) > 10:
        lines.append(f"• و {len(jobs) - 10} پنل دیگر...")

    if target_services <= 0:
        lines.extend(["", "❌ هیچ سرویس قابل اعمالی پیدا نشد."])
    else:
        lines.extend(["", "برای شروع عملیات روی دکمه زیر بزنید."])

    return "\n".join(lines)


def build_progress_message(state: dict, issues: list[str]) -> str:
    total = state["total"] or 0
    processed = state["processed"]
    percent = (processed / total * 100) if total else 100
    lines = [
        "⏳ **در حال اعمال تغییر همگانی...**",
        "",
        f"🔹 محدوده: {state['panel_text']}",
        f"📊 حجم: {state['volume_text']}",
        f"⏰ زمان: {state['time_text']}",
        f"🚀 روش اجرا: {state['mode_text']}",
        "",
        f"🔄 پیشرفت: {processed}/{total} ({percent:.1f}%)",
        f"✅ موفق: {state['success']}",
        f"❌ ناموفق: {state['failed']}",
        f"⚠️ رد شده: {state['skipped']}",
        f"📡 پنل فعلی: {state.get('current_panel', '-')}",
    ]
    if issues:
        lines.extend(["", "🧾 **آخرین موارد قابل بررسی:**"])
        lines.extend(f"• {issue}" for issue in issues[-states.MAX_ERROR_DETAILS :])
    return "\n".join(lines)


def build_result_message(state: dict, issues: list[str]) -> str:
    title = "✅ **تغییر حجم و زمان همگانی تکمیل شد**"
    if state["failed"]:
        title = "⚠️ **تغییر حجم و زمان همگانی با چند خطا تکمیل شد**"

    lines = [
        title,
        "",
        "📋 **نتیجه عملیات:**",
        f"🔹 تعداد پنل‌ها: {state['panel_count']}",
        f"🚀 روش اجرا: {state['mode_text']}",
        f"📊 حجم: {state['volume_text']}",
        f"⏰ زمان: {state['time_text']}",
        f"🔄 سرویس‌های قابل اعمال: {state['total']}",
        f"✅ موفق: {state['success']}",
        f"❌ ناموفق: {state['failed']}",
        f"⚠️ رد شده: {state['skipped']}",
        f"👥 تعداد کاربران: {len(state['affected_users'])}",
        "",
        "📊 **آمار کل:**",
        f"📊 کل تغییر حجم: {format_signed_size_delta(state['total_volume_added'])}",
        f"⏰ کل تغییر زمان: {format_signed_days_delta(state['total_time_added'])}",
        "",
        "📣 اطلاع‌رسانی خودکار ارسال نشد.",
    ]

    if issues:
        lines.extend(["", "🧾 **آخرین موارد قابل بررسی:**"])
        lines.extend(f"• {issue}" for issue in issues[-states.MAX_ERROR_DETAILS :])

    return "\n".join(lines)


def build_log_message(state: dict, admin_id: int) -> str:
    return (
        f"📈 **تغییر حجم و زمان همگانی**\n\n"
        f"👤 ادمین: `{admin_id}`\n"
        f"📋 عملیات: تغییر حجم و/یا زمان سرویس‌ها\n"
        f"📊 مقدار حجم تنظیم‌شده: {state['volume_text']}\n"
        f"⏰ مقدار زمان تنظیم‌شده: {state['time_text']}\n"
        f"🚀 روش اجرا: {state['mode_text']}\n"
        f"🔄 سرویس‌های قابل اعمال: {state['total']}\n"
        f"✅ موفق: {state['success']}\n"
        f"❌ ناموفق: {state['failed']}\n"
        f"⚠️ رد شده: {state['skipped']}\n"
        f"👥 تعداد کاربران: {len(state['affected_users'])}\n\n"
        f"📊 **آمار کل:**\n"
        f"📊 کل تغییر حجم: {format_signed_size_delta(state['total_volume_added'])}\n"
        f"⏰ کل تغییر زمان: {format_signed_days_delta(state['total_time_added'])}"
    )
