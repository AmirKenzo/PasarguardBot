"""Message handlers for admin migration (bot-to-bot data import)."""

import asyncio
import contextlib
import os
import tempfile

from telethon import events
from telethon.tl.custom import Message

from app.logger import get_logger
from app.services.migration import importer
from app.services.migration.base import ParsedMigration
from app.services.migration.registry import ADAPTERS
from app.telegram.admin.migration import cache, keyboards, states, texts
from app.telegram.state import get_data, get_step, set_step
from config import ADMIN_ID

logger = get_logger(__name__)

_MAX_FILE_SIZE = 60 * 1024 * 1024


def _read_and_parse(path: str, adapter) -> ParsedMigration:
    with open(path, encoding="utf-8", errors="replace") as fh:
        sql_text = fh.read()
    return adapter.parse(sql_text)


async def _show_source_menu(event: Message) -> None:
    await set_step(event.sender_id, states.MIGRATION_SOURCE_STEP)
    if not ADAPTERS:
        await event.respond(texts.NO_SOURCES)
        return
    await event.respond(texts.MENU_PROMPT, buttons=keyboards.source_menu_buttons(), parse_mode="md")


async def _migration_message_filter(event: Message) -> bool:
    if event.sender_id not in ADMIN_ID or not event.is_private:
        return False
    msg = (event.message.text or "").strip()
    if msg == states.MIGRATION_MENU_TRIGGER:
        return True
    step = await get_step(event.sender_id)
    return step == states.MIGRATION_AWAIT_FILE_STEP and bool(event.message.document)


async def _handle_uploaded_file(event: Message) -> None:
    document = event.message.document
    file_name = event.message.file.name if event.message.file else ""
    if not (file_name or "").lower().endswith(".sql"):
        await event.respond(texts.NOT_SQL_FILE)
        return
    if document.size and document.size > _MAX_FILE_SIZE:
        await event.respond(texts.FILE_TOO_LARGE)
        return

    slug = await get_data(event.sender_id, states.SOURCE_DATA_KEY)
    adapter = ADAPTERS.get(slug)
    if adapter is None:
        await _show_source_menu(event)
        return

    status = await event.respond(texts.PARSING)
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(suffix=".sql")
        os.close(fd)
        await event.client.download_media(document, file=tmp_path)
        parsed = await asyncio.to_thread(_read_and_parse, tmp_path, adapter)
    except Exception as exc:
        logger.exception("Migration: failed to parse uploaded backup")
        await status.edit(texts.parse_failed_text(str(exc)))
        return
    finally:
        if tmp_path:
            with contextlib.suppress(OSError):
                os.remove(tmp_path)

    await status.edit(texts.CHECKING_PANELS)
    call_count = 0

    async def _progress(status_line: str) -> None:
        nonlocal call_count
        call_count += 1
        if call_count % 3:
            return
        with contextlib.suppress(Exception):
            await status.edit(texts.checking_panels_text(status_line))

    try:
        resolved = await importer.resolve_migration(parsed, progress_cb=_progress)
    except Exception as exc:
        logger.exception("Migration: failed to resolve parsed backup against panels")
        await status.edit(texts.parse_failed_text(str(exc)))
        return

    cache.set_pending(event.sender_id, resolved)
    await set_step(event.sender_id, states.MIGRATION_CONFIRM_STEP)
    await status.edit(texts.preview_text(resolved), buttons=keyboards.confirm_buttons(), parse_mode="md")


async def message_handler_migration(event: Message):
    msg = (event.message.text or "").strip()

    if msg == states.MIGRATION_MENU_TRIGGER:
        await _show_source_menu(event)
        raise events.StopPropagation

    step = await get_step(event.sender_id)
    if step == states.MIGRATION_AWAIT_FILE_STEP and event.message.document:
        await _handle_uploaded_file(event)
        raise events.StopPropagation


def register(client):
    client.add_event_handler(
        message_handler_migration,
        events.NewMessage(incoming=True, func=_migration_message_filter),
    )
