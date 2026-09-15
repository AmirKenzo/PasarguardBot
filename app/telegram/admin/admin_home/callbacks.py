"""Callback handlers for admin home panel."""

import contextlib

from telethon import events

from app.telegram.admin.admin_home.service import send_admin_home
from app.telegram.keyboards.admin import (
    ADMIN_LEAF_PREFIX,
    ADMIN_MENU_PREFIX,
    ADMIN_SECTION_BY_KEY,
    admin_leaf_label,
    admin_section_inline,
)
from app.telegram.shared.utils.menu_router import route_text_press
from config import ADMIN_ID


async def callback_back_to_admin_panel(event: events.CallbackQuery.Event):
    if not event.is_private:
        return
    await event.answer()
    with contextlib.suppress(Exception):
        await event.delete()
    user = await event.get_sender()
    username = user.username if user else None
    await send_admin_home(event.sender_id, username)
    raise events.StopPropagation


async def callback_admin_section(event: events.CallbackQuery.Event):
    """Open a drawer of the in-chat admin menu."""
    key = event.data.decode("utf-8", "ignore").removeprefix(ADMIN_MENU_PREFIX)
    section = ADMIN_SECTION_BY_KEY.get(key)
    await event.answer()
    if section is None:
        return
    await event.respond(section.label, buttons=admin_section_inline(section))
    raise events.StopPropagation


async def callback_admin_leaf(event: events.CallbackQuery.Event):
    """Run the button the press stands for, as if its text had been sent."""
    payload = event.data.decode("utf-8", "ignore").removeprefix(ADMIN_LEAF_PREFIX)
    key, _, raw_index = payload.partition(":")
    await event.answer()
    try:
        label = admin_leaf_label(key, int(raw_index))
    except ValueError:
        return
    if not label:
        return
    await route_text_press(event.client, event, label)
    raise events.StopPropagation


def register(client):
    client.add_event_handler(
        callback_back_to_admin_panel,
        events.CallbackQuery(data="back_to_admin_panel", func=lambda e: e.sender_id in ADMIN_ID),
    )
    client.add_event_handler(
        callback_admin_section,
        events.CallbackQuery(
            func=lambda e: e.sender_id in ADMIN_ID and e.data.decode("utf-8", "ignore").startswith(ADMIN_MENU_PREFIX)
        ),
    )
    client.add_event_handler(
        callback_admin_leaf,
        events.CallbackQuery(
            func=lambda e: e.sender_id in ADMIN_ID and e.data.decode("utf-8", "ignore").startswith(ADMIN_LEAF_PREFIX)
        ),
    )
