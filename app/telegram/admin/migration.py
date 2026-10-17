"""Admin wizard that imports users, panels and services from another bot's ``.sql`` backup.

Flow: pick a source bot -> upload the backup -> preview (checked against the real panels) -> confirm.
The parsed preview is kept in memory per admin; only the step lives in the state store.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import tempfile

from telethon import Button, events
from telethon.tl.custom import Message

from app.logger import get_logger
from app.services.migration import importer
from app.services.migration.base import ParsedMigration
from app.services.migration.importer import ImportResult, ResolvedMigration
from app.services.migration.registry import ADAPTERS
from app.telegram.plugins import PluginContext
from app.telegram.state import get_data, get_step, set_data, set_step
from config import ADMIN_ID

MODULE_NAME = "admin.migration"
MODULE_DESCRIPTION = "Admin bot-to-bot data migration wizard"

logger = get_logger(__name__)

MENU_TRIGGER = "🧬 مایگریشن از ربات دیگر"
SOURCE_STEP = "migration_source"
AWAIT_FILE_STEP = "migration_await_file"
CONFIRM_STEP = "migration_confirm_step"
SOURCE_DATA_KEY = "migration_source_slug"

SOURCE_PREFIX = "migration_source:"
MENU_CALLBACK = "migration_menu"
CONFIRM_CALLBACK = "migration_confirm"
CANCEL_CALLBACK = "migration_cancel"

MAX_FILE_SIZE = 60 * 1024 * 1024
IMPORT_PROGRESS_EVERY = 15
RESOLVE_PROGRESS_EVERY = 3

MENU_PROMPT = (
    "🧬 **مایگریشن از ربات دیگر**\n\n"
    "🔹 این ابزار کاربران، پنل‌ها و سرویس‌های یک ربات دیگر را از روی فایل بکاپ `.sql` وارد این ربات می‌کند.\n"
    "🔹 ابتدا نوع ربات مبدا را انتخاب کنید:"
)
PANEL_STATUS_LABELS = {
    "existing": "✅ از قبل در ربات ثبت شده",
    "ok": "✅ ورود موفق",
    "login_failed": "❌ ورود ناموفق",
}

_pending: dict[int, ResolvedMigration] = {}


def _source_buttons() -> list:
    rows = [[Button.inline(adapter.display_name, data=f"{SOURCE_PREFIX}{slug}")] for slug, adapter in ADAPTERS.items()]
    return [*rows, *_back_buttons()]


def _confirm_buttons() -> list:
    return [
        [Button.inline("✅ تایید و شروع وارد کردن", data=CONFIRM_CALLBACK)],
        [Button.inline("❌ لغو", data=CANCEL_CALLBACK)],
    ]


def _back_buttons() -> list:
    return [[Button.inline("🔙 بازگشت به پنل", data="back_to_admin_panel")]]


def _throttled(every: int, edit):
    """Progress callback that forwards only every ``every``-th update to ``edit``."""
    calls = 0

    async def progress(status_line: str) -> None:
        nonlocal calls
        calls += 1
        if calls % every == 0:
            with contextlib.suppress(Exception):
                await edit(status_line)

    return progress


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
    for panel in resolved.panels:
        line = f"• {panel.source_panel.name} — {PANEL_STATUS_LABELS[panel.status]}"
        if panel.status == "login_failed":
            line += f" ({panel.login_error})"
        else:
            line += (
                f" — یافت‌شده روی پنل: `{panel.services_matched_count}` از "
                f"`{panel.services_dump_count}` سرویس فعال در دیتابیس"
            )
        lines.append(line)

    lines += [
        "",
        f"🧩 مجموع سرویس‌های فعال در دیتابیس مبدا: `{resolved.services_dump_total}`",
        f"✅ سرویس‌هایی که واقعاً روی پنل تایید شدند و وارد می‌شوند: `{resolved.services_matched_total}`",
    ]
    if resolved.services_inactive_in_source:
        lines.append(f"⏭ نادیده‌گرفته‌شده (غیرفعال در دیتابیس مبدا): `{resolved.services_inactive_in_source}`")
    if parsed.skipped_services:
        lines.append(f"⏭ نادیده‌گرفته‌شده (بدون پنل معتبر یا شناسه): `{parsed.skipped_services}`")
    lines += ["", "اگر اعداد بالا درست به نظر می‌رسند، برای شروع وارد کردن اطلاعات تایید کنید."]
    return "\n".join(lines)


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
        lines += ["", "🧾 **موارد قابل بررسی:**", *(f"• {issue}" for issue in result.issues[-10:])]
    return "\n".join(lines)


def _read_and_parse(path: str, adapter) -> ParsedMigration:
    with open(path, encoding="utf-8", errors="replace") as fh:
        return adapter.parse(fh.read())


async def _show_source_menu(event: Message) -> None:
    await set_step(event.sender_id, SOURCE_STEP)
    if not ADAPTERS:
        await event.respond("❌ هیچ منبع مایگریشنی تعریف نشده است.")
        return
    await event.respond(MENU_PROMPT, buttons=_source_buttons(), parse_mode="md")


async def _handle_upload(event: Message) -> None:
    document = event.message.document
    file_name = event.message.file.name if event.message.file else ""
    if not (file_name or "").lower().endswith(".sql"):
        await event.respond("⚠️ فقط فایل با پسوند `.sql` پذیرفته می‌شود.")
        return
    if document.size and document.size > MAX_FILE_SIZE:
        await event.respond("⚠️ حجم فایل بیش از حد مجاز است.")
        return

    adapter = ADAPTERS.get(await get_data(event.sender_id, SOURCE_DATA_KEY))
    if adapter is None:
        await _show_source_menu(event)
        return

    status = await event.respond("⏳ در حال خواندن فایل بکاپ...")
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(suffix=".sql")
        os.close(fd)
        await event.client.download_media(document, file=tmp_path)
        parsed = await asyncio.to_thread(_read_and_parse, tmp_path, adapter)
    except Exception as exc:
        logger.exception("Migration: failed to parse uploaded backup")
        await status.edit(f"❌ خطا در خواندن فایل:\n`{exc}`")
        return
    finally:
        if tmp_path:
            with contextlib.suppress(OSError):
                os.remove(tmp_path)

    await status.edit("⏳ در حال بررسی پنل‌ها و استعلام سرویس‌ها...")
    progress = _throttled(RESOLVE_PROGRESS_EVERY, lambda line: status.edit(f"⏳ **در حال بررسی پنل‌ها...**\n\n{line}"))
    try:
        resolved = await importer.resolve_migration(parsed, progress_cb=progress)
    except Exception as exc:
        logger.exception("Migration: failed to resolve parsed backup against panels")
        await status.edit(f"❌ خطا در خواندن فایل:\n`{exc}`")
        return

    _pending[event.sender_id] = resolved
    await set_step(event.sender_id, CONFIRM_STEP)
    await status.edit(preview_text(resolved), buttons=_confirm_buttons(), parse_mode="md")


async def _run_import(event: events.CallbackQuery.Event) -> None:
    admin_id = event.sender_id
    resolved = _pending.get(admin_id)
    if resolved is None:
        await event.answer("داده‌ای برای وارد کردن یافت نشد. دوباره فایل را ارسال کنید.", alert=True)
        return

    await event.answer()
    progress_screen = "⏳ **در حال اجرای مایگریشن...**\n\n{}"
    await event.edit(progress_screen.format("⏳ در حال وارد کردن اطلاعات..."))
    progress = _throttled(IMPORT_PROGRESS_EVERY, lambda line: event.edit(progress_screen.format(line)))
    try:
        result = await importer.commit_migration(resolved, progress_cb=progress)
    except Exception:
        logger.exception("Migration: import run failed")
        await event.edit("❌ اجرای مایگریشن با خطا متوقف شد. لاگ سرور را بررسی کنید.", buttons=_back_buttons())
        return
    finally:
        _pending.pop(admin_id, None)

    await set_step(admin_id, SOURCE_STEP)
    await event.edit(result_text(result), buttons=_back_buttons(), parse_mode="md")


async def _message_filter(event: Message) -> bool:
    if event.sender_id not in ADMIN_ID or not event.is_private:
        return False
    if (event.message.text or "").strip() == MENU_TRIGGER:
        return True
    return bool(event.message.document) and await get_step(event.sender_id) == AWAIT_FILE_STEP


async def migration_message(event: Message) -> None:
    if (event.message.text or "").strip() == MENU_TRIGGER:
        await _show_source_menu(event)
    else:
        await _handle_upload(event)
    raise events.StopPropagation


def _callback_filter(event: events.CallbackQuery.Event) -> bool:
    if event.sender_id not in ADMIN_ID:
        return False
    data = event.data.decode()
    return data in (MENU_CALLBACK, CONFIRM_CALLBACK, CANCEL_CALLBACK) or data.startswith(SOURCE_PREFIX)


async def migration_callback(event: events.CallbackQuery.Event) -> None:
    data = event.data.decode()
    admin_id = event.sender_id

    if data == CONFIRM_CALLBACK:
        await _run_import(event)
        return

    if data.startswith(SOURCE_PREFIX):
        slug = data.removeprefix(SOURCE_PREFIX)
        adapter = ADAPTERS.get(slug)
        if adapter is None:
            await event.answer("منبع نامعتبر است.", alert=True)
            return
        await set_data(admin_id, SOURCE_DATA_KEY, slug)
        await set_step(admin_id, AWAIT_FILE_STEP)
        await event.edit(
            f"📤 فایل بکاپ **{adapter.display_name}** را به‌صورت `.sql` ارسال کنید.",
            buttons=_back_buttons(),
            parse_mode="md",
        )
        return

    _pending.pop(admin_id, None)
    await set_step(admin_id, SOURCE_STEP)
    text = MENU_PROMPT if data == MENU_CALLBACK else "❌ عملیات مایگریشن لغو شد."
    await event.edit(text, buttons=_source_buttons(), parse_mode="md")


def setup(ctx: PluginContext) -> None:
    ctx.add_event_handler(migration_message, events.NewMessage(incoming=True, func=_message_filter))
    ctx.add_event_handler(migration_callback, events.CallbackQuery(func=_callback_filter))
