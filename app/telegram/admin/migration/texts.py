"""Text templates for admin migration."""

from app.services.migration.base import ParsedMigration
from app.services.migration.importer import ImportResult

MENU_PROMPT = (
    "🧬 **مایگریشن از ربات دیگر**\n\n"
    "🔹 این ابزار کاربران، پنل‌ها و سرویس‌های یک ربات دیگر را از روی فایل بکاپ `.sql` وارد این ربات می‌کند.\n"
    "🔹 ابتدا نوع ربات مبدا را انتخاب کنید:"
)
NO_SOURCES = "❌ هیچ منبع مایگریشنی تعریف نشده است."
NOT_SQL_FILE = "⚠️ فقط فایل با پسوند `.sql` پذیرفته می‌شود."
FILE_TOO_LARGE = "⚠️ حجم فایل بیش از حد مجاز است."
PARSING = "⏳ در حال خواندن و تحلیل فایل بکاپ..."
CANCELLED = "❌ عملیات مایگریشن لغو شد."
IMPORTING_STARTED = "⏳ در حال وارد کردن اطلاعات..."
NO_PENDING_DATA = "داده‌ای برای وارد کردن یافت نشد. دوباره فایل را ارسال کنید."
IMPORT_FAILED = "❌ اجرای مایگریشن با خطا متوقف شد. لاگ سرور را بررسی کنید."


def parse_failed_text(error: str) -> str:
    return f"❌ خطا در خواندن فایل:\n`{error}`"


def await_file_prompt(source_label: str) -> str:
    return f"📤 فایل بکاپ **{source_label}** را به‌صورت `.sql` ارسال کنید."


def preview_text(parsed: ParsedMigration) -> str:
    lines = [
        f"🧬 **پیش‌نمایش مایگریشن از {parsed.source_label}**",
        "",
        f"👥 کاربران یافت‌شده: `{len(parsed.users)}`",
        f"🖥 پنل‌های پاسارگارد یافت‌شده: `{len(parsed.panels)}`"
        + (f" (نادیده‌گرفته‌شده: `{parsed.skipped_panels}`)" if parsed.skipped_panels else ""),
        f"🧩 سرویس‌های متصل به این پنل‌ها: `{len(parsed.services)}`"
        + (f" (نادیده‌گرفته‌شده: `{parsed.skipped_services}`)" if parsed.skipped_services else ""),
        "",
        "⚠️ در مرحله اجرا، وضعیت دقیق هر سرویس (انقضا، حجم، فعال بودن) مستقیماً از پنل استعلام می‌شود؛ "
        "سرویس‌هایی که دیگر روی پنل وجود ندارند وارد نخواهند شد.",
        "",
        "برای شروع وارد کردن اطلاعات، تایید کنید.",
    ]
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
