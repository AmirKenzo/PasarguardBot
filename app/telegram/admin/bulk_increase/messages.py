"""Message handlers for admin bulk_increase."""

import contextlib
import math

from telethon import events
from telethon.tl.custom import Message

from app import Kenzo
from app.db.crud.panels import PanelsManager
from app.telegram.admin.bulk_increase import keyboards, states, texts
from app.telegram.keyboards.admin import panel_back
from app.telegram.state import delete_data, get_data, get_step, set_data, set_step
from config import ADMIN_ID


def is_number(msg: str) -> bool:
    try:
        return math.isfinite(float(msg))
    except (TypeError, ValueError):
        return False


async def _respond_with_optional_edit(
    user_id: int,
    last_msg_id: str | None,
    message_text: str,
    buttons,
) -> None:
    if last_msg_id:
        try:
            await Kenzo.edit_message(
                entity=user_id,
                message=int(last_msg_id),
                text=message_text,
                buttons=buttons,
            )
            await delete_data(user_id, states.STEP_KEY_LAST_MSG_ID)
            return
        except Exception:
            pass
    await Kenzo.send_message(entity=user_id, message=message_text, buttons=buttons)


async def bulk_increase_message_handler(event: Message):
    """Handle bulk increase volume and time messages"""
    if not event.is_private:
        return

    msg = event.message.text
    if not msg:
        return

    if msg == states.BULK_INCREASE_MENU_MESSAGE:
        panels = await PanelsManager().get_all_panels_reverse()
        if not panels:
            await Kenzo.send_message(
                entity=event.sender_id,
                message=texts.NO_PANELS_ERROR,
                buttons=panel_back,
            )
            return

        await Kenzo.send_message(
            entity=event.sender_id,
            message=texts.PANEL_SELECT_PROMPT,
            buttons=keyboards.panel_selection_buttons(panels),
        )

    elif await get_step(event.sender_id) == states.BULK_INCREASE_VOLUME_STEP:
        with contextlib.suppress(Exception):
            await event.delete()

        last_msg_id = await get_data(event.sender_id, states.STEP_KEY_LAST_MSG_ID)

        if not is_number(event.message.text):
            await _respond_with_optional_edit(
                event.sender_id,
                last_msg_id,
                texts.VOLUME_INPUT_ERROR,
                panel_back,
            )
            return

        volume = float(event.message.text)
        if volume == 0:
            await _respond_with_optional_edit(
                event.sender_id,
                last_msg_id,
                texts.VOLUME_ZERO_ERROR,
                panel_back,
            )
            return

        await set_data(event.sender_id, states.STEP_KEY_VOLUME, str(volume))
        await set_step(event.sender_id, states.PANEL_STEP)

        panel_code_str = await get_data(event.sender_id, states.STEP_KEY_PANEL)
        time_days = await get_data(event.sender_id, states.STEP_KEY_TIME)
        volume_text, time_text = texts.operation_texts(str(volume), time_days)
        message_text = texts.settings_menu_text(panel_code_str, volume_text, time_text)

        await _respond_with_optional_edit(
            event.sender_id,
            last_msg_id,
            message_text,
            keyboards.settings_menu_buttons(),
        )

    elif await get_step(event.sender_id) == states.BULK_INCREASE_TIME_STEP:
        with contextlib.suppress(Exception):
            await event.delete()

        last_msg_id = await get_data(event.sender_id, states.STEP_KEY_LAST_MSG_ID)

        time_days = texts.parse_day_amount(event.message.text)
        if time_days is None:
            await _respond_with_optional_edit(
                event.sender_id,
                last_msg_id,
                texts.TIME_INPUT_ERROR,
                panel_back,
            )
            return

        if time_days == 0:
            await _respond_with_optional_edit(
                event.sender_id,
                last_msg_id,
                texts.TIME_ZERO_ERROR,
                panel_back,
            )
            return

        await set_data(event.sender_id, states.STEP_KEY_TIME, str(time_days))
        await set_step(event.sender_id, states.PANEL_STEP)

        panel_code_str = await get_data(event.sender_id, states.STEP_KEY_PANEL)
        volume = await get_data(event.sender_id, states.STEP_KEY_VOLUME)
        volume_text, time_text = texts.operation_texts(volume, str(time_days))
        message_text = texts.settings_menu_text(panel_code_str, volume_text, time_text)

        await _respond_with_optional_edit(
            event.sender_id,
            last_msg_id,
            message_text,
            keyboards.settings_menu_buttons(),
        )


async def _bulk_increase_message_filter(event: Message) -> bool:
    if event.sender_id not in ADMIN_ID or not event.is_private:
        return False
    msg = (event.message.text or "").strip()
    if msg == states.BULK_INCREASE_MENU_MESSAGE:
        return True
    step = (await get_step(event.sender_id)) or ""
    return step in (states.BULK_INCREASE_VOLUME_STEP, states.BULK_INCREASE_TIME_STEP) and bool(msg)


def register(client):
    client.add_event_handler(
        bulk_increase_message_handler,
        events.NewMessage(incoming=True, from_users=ADMIN_ID, func=_bulk_increase_message_filter),
    )
