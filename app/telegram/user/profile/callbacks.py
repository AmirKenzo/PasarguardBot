"""Callback handlers for user profile."""

from telethon import events

from app.db.crud.user import UserCRUD
from app.telegram.keyboards.home import home_back_button
from app.telegram.shared.utils.maintenance import bot_is_offline
from app.telegram.shared.utils.rate_limit import debounce_callback
from app.telegram.state import set_step
from app.telegram.user.profile import states
from app.telegram.user.profile.messages import _build_profile_message


@bot_is_offline
@debounce_callback()
async def callback_back_to_profile(event: events.CallbackQuery.Event):
    user_id = event.sender_id
    await set_step(user_id=user_id, step=states.STEP_MAIN)
    info = await UserCRUD().read_user(user_id)
    profile_message = await _build_profile_message(user_id, info)
    await event.edit(profile_message, buttons=[[home_back_button()]])


def register(client):
    client.add_event_handler(
        callback_back_to_profile,
        events.CallbackQuery(data=states.CALLBACK_BACK_TO_PROFILE),
    )
