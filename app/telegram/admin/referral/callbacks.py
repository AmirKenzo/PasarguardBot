"""Callback handlers for admin referral system management."""

from telethon import events

from app.telegram.admin.referral import service, states
from config import ADMIN_ID


def referral_callback_filter(event: events.CallbackQuery.Event) -> bool:
    data = event.data.decode("utf-8")
    if data in states.REFERRAL_USER_CALLBACKS:
        return True
    if data in states.REFERRAL_ADMIN_CALLBACKS:
        return event.sender_id in ADMIN_ID
    return False


async def callback_referral(event: events.CallbackQuery.Event):
    data = event.data.decode("utf-8")
    await service.handle_referral_callbacks(event, data)
    raise events.StopPropagation


def register(client):
    client.add_event_handler(callback_referral, events.CallbackQuery(func=referral_callback_filter))
