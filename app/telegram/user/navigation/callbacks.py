"""Callback handlers for shared user navigation."""

from __future__ import annotations

import contextlib

from telethon import events

from app.telegram.keyboards.home import bhome_buttons
from app.telegram.shared.guards.callback_guards import SESSION_RESTART_CALLBACK
from app.telegram.shared.utils.maintenance import bot_is_offline
from app.telegram.shared.utils.rate_limit import debounce_callback
from app.telegram.state import clear_user, set_step
from app.telegram.user.start.helpers import fetch_welcome_text, get_user_lang


@bot_is_offline
@debounce_callback()
async def data_cancel_callback(event: events.CallbackQuery.Event):
    lang = await get_user_lang(event.sender_id)
    txt = await fetch_welcome_text(lang)
    await event.delete()
    await event.respond(txt, buttons=await bhome_buttons(event.sender_id, lang))
    await set_step(event.sender_id, step="home")
    raise events.StopPropagation


@bot_is_offline
@debounce_callback()
async def session_restart_callback(event: events.CallbackQuery.Event):
    await clear_user(event.sender_id)
    lang = await get_user_lang(event.sender_id)
    txt = await fetch_welcome_text(lang)
    with contextlib.suppress(Exception):
        await event.delete()
    await event.respond(txt, buttons=await bhome_buttons(event.sender_id, lang))
    await set_step(event.sender_id, step="home")
    raise events.StopPropagation


@bot_is_offline
async def callback_noop_disabled(event: events.CallbackQuery.Event):
    await event.answer(message="⛔ این قابلیت هنوز فعال نشده است.", alert=False)


@bot_is_offline
async def callback_noop_ghost(event: events.CallbackQuery.Event):
    await event.answer(message="👻", alert=False)


def register(client):
    client.add_event_handler(
        data_cancel_callback,
        events.CallbackQuery(data="DataCancel"),
    )
    client.add_event_handler(
        session_restart_callback,
        events.CallbackQuery(data=SESSION_RESTART_CALLBACK),
    )
    client.add_event_handler(
        callback_noop_disabled,
        events.CallbackQuery(data="none"),
    )
    client.add_event_handler(
        callback_noop_ghost,
        events.CallbackQuery(data="no_action"),
    )
