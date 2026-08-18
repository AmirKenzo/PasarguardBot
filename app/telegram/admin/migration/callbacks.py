"""Callback handlers for admin migration."""

import contextlib

from telethon import events

from app.logger import get_logger
from app.services.migration import importer
from app.services.migration.registry import ADAPTERS
from app.telegram.admin.migration import cache, keyboards, states, texts
from app.telegram.state import set_data, set_step
from config import ADMIN_ID

logger = get_logger(__name__)


def _migration_callback_filter(event: events.CallbackQuery.Event) -> bool:
    if event.sender_id not in ADMIN_ID:
        return False
    data = event.data.decode("utf-8")
    if data in (states.MIGRATION_MENU_CALLBACK, states.MIGRATION_CONFIRM_CALLBACK, states.MIGRATION_CANCEL_CALLBACK):
        return True
    return data.startswith(states.MIGRATION_SOURCE_PREFIX)


async def _run_confirmed_import(event: events.CallbackQuery.Event) -> None:
    admin_id = event.sender_id
    resolved = cache.get_pending(admin_id)
    if resolved is None:
        await event.answer(texts.NO_PENDING_DATA, alert=True)
        return

    await event.answer()
    await event.edit(texts.progress_text(texts.IMPORTING_STARTED))

    call_count = 0

    async def _progress(status_line: str) -> None:
        nonlocal call_count
        call_count += 1
        if call_count % states.PROGRESS_EDIT_INTERVAL:
            return
        with contextlib.suppress(Exception):
            await event.edit(texts.progress_text(status_line))

    try:
        result = await importer.commit_migration(resolved, progress_cb=_progress)
    except Exception:
        logger.exception("Migration: import run failed")
        await event.edit(texts.IMPORT_FAILED, buttons=keyboards.back_buttons())
        cache.clear_pending(admin_id)
        return

    cache.clear_pending(admin_id)
    await set_step(admin_id, states.MIGRATION_SOURCE_STEP)
    await event.edit(texts.result_text(result), buttons=keyboards.back_buttons(), parse_mode="md")


async def callback_migration(event: events.CallbackQuery.Event):
    data = event.data.decode("utf-8")
    admin_id = event.sender_id

    if data == states.MIGRATION_MENU_CALLBACK:
        cache.clear_pending(admin_id)
        await set_step(admin_id, states.MIGRATION_SOURCE_STEP)
        await event.edit(texts.MENU_PROMPT, buttons=keyboards.source_menu_buttons(), parse_mode="md")
        return

    if data.startswith(states.MIGRATION_SOURCE_PREFIX):
        slug = data[len(states.MIGRATION_SOURCE_PREFIX) :]
        adapter = ADAPTERS.get(slug)
        if adapter is None:
            await event.answer("منبع نامعتبر است.", alert=True)
            return
        await set_data(admin_id, states.SOURCE_DATA_KEY, slug)
        await set_step(admin_id, states.MIGRATION_AWAIT_FILE_STEP)
        await event.edit(
            texts.await_file_prompt(adapter.display_name), buttons=keyboards.back_buttons(), parse_mode="md"
        )
        return

    if data == states.MIGRATION_CANCEL_CALLBACK:
        cache.clear_pending(admin_id)
        await set_step(admin_id, states.MIGRATION_SOURCE_STEP)
        await event.edit(texts.CANCELLED, buttons=keyboards.source_menu_buttons(), parse_mode="md")
        return

    if data == states.MIGRATION_CONFIRM_CALLBACK:
        await _run_confirmed_import(event)


def register(client):
    client.add_event_handler(
        callback_migration,
        events.CallbackQuery(func=_migration_callback_filter),
    )
