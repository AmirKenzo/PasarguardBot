"""Message handlers for user profile."""

from telethon import events
from telethon.tl.custom import Message

from app import Kenzo
from app.db.crud.discount_codes import DiscountCodeManager
from app.db.crud.keyboards import get_button_text
from app.db.crud.user import UserCRUD
from app.services.billing.sticky_discount import format_profile_sticky_discount, get_sticky_discount
from app.telegram.keyboards.common import is_keyboard_config_step
from app.telegram.shared.guards.channel_gate import ensure_channel_membership
from app.telegram.shared.url_presets import get_bot_username
from app.telegram.shared.utils.maintenance import bot_is_offline
from app.telegram.state import get_step
from app.telegram.user.profile import keyboards, states, texts
from app.utils.formatting.dates import Time_Date


async def _build_discount_status(user_id: int) -> str:
    sticky = await get_sticky_discount(user_id)
    if sticky and sticky.is_public:
        bot_username = await get_bot_username(Kenzo)
        return format_profile_sticky_discount(sticky, bot_username)

    discount_code_status = await DiscountCodeManager().get_code_whith_user_id(user_id)
    if discount_code_status is False:
        return states.NO_DISCOUNT_CODE_TEXT
    return texts.discount_code_text(discount_code_status)


async def _build_profile_message(user_id: int, info) -> str:
    date_message = Time_Date(info.time_s) if info.time_s else {"jf": states.DATE_NOT_REGISTERED}
    discount_status = await _build_discount_status(user_id)
    if info.number is None:
        info.number = states.PHONE_NOT_REGISTERED
    return texts.profile_message(
        user_id,
        info,
        date_message["jf"],
        discount_status,
    )


async def menu_profile_filter(event):
    if event.is_channel:
        return False
    if is_keyboard_config_step(await get_step(event.sender_id)):
        return False
    msg = event.message.message or ""
    profile_text = await get_button_text("bt.menu_profile", "🙍 پروفایل من")
    return msg in states.PROFILE_MENU_ALIASES | {profile_text}


@bot_is_offline
async def menu_profile(event: Message):
    if not await ensure_channel_membership(event):
        raise events.StopPropagation

    user_id = event.sender_id
    info = await UserCRUD().read_user(user_id)
    profile_message = await _build_profile_message(user_id, info)
    profile_buttons = keyboards.profile_buttons(info, None)

    await event.respond(profile_message, buttons=profile_buttons if profile_buttons else None)
    raise events.StopPropagation


def register(client):
    client.add_event_handler(
        menu_profile,
        events.NewMessage(incoming=True, func=menu_profile_filter),
    )
