"""Text templates for admin migration."""

from app.services.migration.importer import ImportResult, ResolvedMigration

MENU_PROMPT = (
    "🧬 **مایگریشن از ربات دیگر**\n\n"
    "🔹 این ابزار کاربران، پنل‌ها و سرویس‌های یک ربات دیگر را از روی فایل بکاپ `.sql` وارد این ربات می‌کند.\n"
    "🔹 ابتدا نوع ربات مبدا را انتخاب کنید:"
)
NO_SOURCES = "❌ هیچ منبع مایگریشنی تعریف نشده است."
NOT_SQL_FILE = "⚠️ فقط فایل با پسوند `.sql` پذیرفته می‌شود."
FILE_TOO_LARGE = "⚠️ حجم فایل بیش از حد مجاز است."
PARSING = "⏳ در حال خواندن فایل بکاپ..."
CHECKING_PANELS = "⏳ در حال بررسی پنل‌ها و استعلام سرویس‌ها..."
CANCELLED = "❌ عملیات مایگریشن لغو شد."
IMPORTING_STARTED = "⏳ در حال وارد کردن اطلاعات..."
NO_PENDING_DATA = "داده‌ای برای وارد کردن یافت نشد. دوباره فایل را ارسال کنید."
IMPORT_FAILED = "❌ اجرای مایگریشن با خطا متوقف شد. لاگ سرور را بررسی کنید."

_PANEL_STATUS_LABEL = {
    "existing": "✅ از قبل در ربات ثبت شده",
    "ok": "✅ ورود موفق",
    "login_failed": "❌ ورود ناموفق",
}


def parse_failed_text(error: str) -> str:
    return f"❌ خطا در خواندن فایل:\n`{error}`"


def await_file_prompt(source_label: str) -> str:
    return f"📤 فایل بکاپ **{source_label}** را به‌صورت `.sql` ارسال کنید."


def checking_panels_text(status_line: str) -> str:
    return f"⏳ **در حال بررسی پنل‌ها...**\n\n{status_line}"


def preview_text(resolved: ResolvedMigration) -> str:
    parsed = resolved.parsed
    lines = [
        f"🧬 **پیش‌نمایش مایگریشن از {parsed.source_label}**",
        "",
        f"👥 کاربران یافت‌شده: `{len(parsed.users)}` (جدید: `{resolved.users_new}`، از قبل موجود: `{resolved.users_existing}`)",
        f"🖥 پنل‌های یافت‌شده: `{len(parsed.panels)}`"
        + (f" (نادیده‌گرفته‌شده: `{parsed.skipped_panels}`)" if parsed.skipped_panels else ""),
        "",
        "📋 **وضعیت پنل‌ها (بررسی‌شده روی پنل واقعی):**",
    ]
    for rp in resolved.panels:
        status_label = _PANEL_STATUS_LABEL[rp.status]
        line = f"• {rp.source_panel.name} — {status_label}"
        if rp.status == "login_failed":
            line += f" ({rp.login_error})"
        else:
            line += (
                f" — یافت‌شده روی پنل: `{rp.services_matched_count}` از `{rp.services_dump_count}` سرویس فعال در دیتابیس"
            )
        lines.append(line)

    lines.extend(
        [
            "",
            f"🧩 مجموع سرویس‌های فعال در دیتابیس مبدا: `{resolved.services_dump_total}`",
            f"✅ سرویس‌هایی که واقعاً روی پنل تایید شدند و وارد می‌شوند: `{resolved.services_matched_total}`",
        ]
    )
    if resolved.services_inactive_in_source:
        lines.append(f"⏭ نادیده‌گرفته‌شده (غیرفعال در دیتابیس مبدا): `{resolved.services_inactive_in_source}`")
    if parsed.skipped_services:
        lines.append(f"⏭ نادیده‌گرفته‌شده (بدون پنل معتبر یا شناسه): `{parsed.skipped_services}`")

    lines.extend(["", "اگر اعداد بالا درست به نظر می‌رسند، برای شروع وارد کردن اطلاعات تایید کنید."])
    return "\n".join(lines)


def progress_text(status_line: str) -> str:
    return f"⏳ **در حال اجرای مایگریشن...**\n\n{status_line}"


def result_text(result: ImportResult) -> str:
    lines = [
        "⚠️ **مایگریشن با چند خطا به پایان رسید**" if result.issues else "✅ **مایگریشن به پایان رسید**",
        "",
        "👥 **کاربران:**",
        f"➕ اضافه شد: `{result.users_created}`",
        f"⏭ از قبل موجود بود: `{result.users_skipped}`",
        "",
        "🖥 **پنل‌ها:**",
        f"➕ اضافه شد: `{result.panels_created}`",
        f"⏭ از قبل موجود بود: `{result.panels_skipped_existing}`",
        f"❌ ورود ناموفق: `{result.panels_failed_login}`",
        "",
        "🧩 **سرویس‌ها:**",
        f"➕ اضافه شد: `{result.services_created}`",
        f"⏭ از قبل موجود بود: `{result.services_skipped_existing}`",
        f"❓ روی پنل پیدا نشد: `{result.services_unmatched_on_panel}`",
    ]
    if result.issues:
        lines.extend(["", "🧾 **موارد قابل بررسی:**"])
        lines.extend(f"• {issue}" for issue in result.issues[-10:])
    return "\n".join(lines)
