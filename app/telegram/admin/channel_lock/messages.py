"""Message handlers for admin channel_lock."""

from telethon import events, utils
from telethon.tl.custom import Message
from telethon.tl.types import Channel as ChannelType, PeerChannel

from app import Kenzo
from app.db.crud.channels import ChannelManager
from app.logger import get_logger
from app.telegram.admin.channel_lock import keyboards, states, texts
from app.telegram.shared.utils.channels import (
    botapi_create_invite_link,
    check_bot_channel_access,
    parse_telegram_message_link,
    resolve_lock_channel_from_input,
)
from app.telegram.state import clear_user, get_data, get_step, set_data, set_step
from config import ADMIN_ID

logger = get_logger(__name__)


async def _legacy_channel_lock_message_filter(event: Message) -> bool:
    if event.sender_id not in ADMIN_ID or not event.is_private:
        return False
    msg = (event.message.text or "").strip()
    if msg == states.LEGACY_ADD_CHANNEL_MESSAGE:
        return True
    step = (await get_step(event.sender_id)) or ""
    return step in states.LEGACY_CHANNEL_LOCK_STEPS and bool(msg)


async def message_handler_channel_lock(event: Message):
    """Handle the channel lock button click"""
    if not event.is_private:
        return
    if await get_step(event.sender_id) != states.PANEL_STEP:
        return

    logger.info("message_handler_channel_lock")

    channel_manager = ChannelManager()
    channels = await channel_manager.get_all_channels()
    channel_count = len(channels) if channels else 0

    await event.respond(
        texts.main_menu_text(channel_count),
        buttons=keyboards.main_menu_buttons(),
    )


async def message_handler_add_channel(event: Message):
    """Handle adding channel - process user input"""
    if not event.is_private:
        return

    if await get_step(event.sender_id) != states.LOCK_ADD_CHANNEL_STEP:
        return

    msg = event.message.text
    channel_info = None
    error_msg = None

    if event.message.forward:
        try:
            forwarded_entity = None
            channel_id = None

            if event.message.forward.chat:
                forwarded_entity = event.message.forward.chat
                if isinstance(forwarded_entity, ChannelType):
                    channel_id = utils.get_peer_id(forwarded_entity)

            if (
                not forwarded_entity
                and event.message.forward.from_id
                and isinstance(event.message.forward.from_id, PeerChannel)
            ):
                channel_id = event.message.forward.from_id.channel_id
                channel_id = int(f"-100{channel_id}")
                try:
                    forwarded_entity = await Kenzo.get_entity(channel_id)
                except Exception as e:
                    logger.error(f"Error getting entity from from_id: {e}")

            if not forwarded_entity and hasattr(event.message.forward, "from_id"):
                from_id_obj = event.message.forward.from_id

                if isinstance(from_id_obj, PeerChannel):
                    channel_id = from_id_obj.channel_id
                    channel_id = int(f"-100{channel_id}")
                    try:
                        forwarded_entity = await Kenzo.get_entity(channel_id)
                    except Exception as e:
                        logger.error(f"Error getting entity from MessageFwdHeader.from_id: {e}")

            if forwarded_entity and isinstance(forwarded_entity, ChannelType):
                if not channel_id:
                    channel_id = utils.get_peer_id(forwarded_entity)

                title = forwarded_entity.title or texts.DEFAULT_CHANNEL_TITLE

                if forwarded_entity.username:
                    link = f"https://t.me/{forwarded_entity.username}"
                    channel_info = {"id": channel_id, "title": title, "link": link}
                else:
                    has_access, access_error = await check_bot_channel_access(Kenzo, channel_id)
                    if not has_access:
                        await event.respond(texts.bot_no_access_text(access_error, private_hint=True))
                        return

                    invite_link, invite_error = await botapi_create_invite_link(channel_id, name="KK Lock")
                    if not invite_link:
                        await event.respond(texts.invite_link_error_text(invite_error))
                        return
                    link = invite_link
                    channel_info = {"id": channel_id, "title": title, "link": link}
            else:
                await event.respond(texts.FORWARD_NOT_CHANNEL)
                return
        except Exception as e:
            logger.error(f"Error processing forwarded message: {e}")
            await event.respond(texts.forward_process_error_text(e))
            return

    elif msg:
        parsed = parse_telegram_message_link(msg)
        if parsed:
            chat_id, _topic_id = parsed
            try:
                entity = await Kenzo.get_entity(chat_id)
                if isinstance(entity, ChannelType):
                    title = entity.title or texts.PRIVATE_CHANNEL_TITLE

                    has_access, access_error = await check_bot_channel_access(Kenzo, chat_id)
                    if not has_access:
                        await event.respond(texts.bot_no_access_text(access_error))
                        return

                    invite_link, invite_error = await botapi_create_invite_link(chat_id, name="KK Lock")
                    if not invite_link:
                        await event.respond(texts.invite_link_error_simple_text(invite_error))
                        return

                    channel_info = {"id": chat_id, "title": title, "link": invite_link}
            except Exception as e:
                logger.error(f"Error resolving channel from message link: {e}")
                await event.respond(texts.channel_resolve_error_text(e))
                return
        else:
            channel_info, error_msg = await resolve_lock_channel_from_input(Kenzo, msg)

            if channel_info:
                has_access, access_error = await check_bot_channel_access(Kenzo, channel_info["id"])
                if not has_access:
                    await event.respond(texts.bot_no_access_text(access_error))
                    return

                link = channel_info.get("link", "")
                is_public = link.startswith("https://t.me/") and not (
                    link.startswith("https://t.me/c/")
                    or link.startswith("https://t.me/+")
                    or link.startswith("https://t.me/joinchat/")
                )

                if not is_public:
                    invite_link, invite_error = await botapi_create_invite_link(channel_info["id"], name="KK Lock")
                    if invite_link:
                        channel_info["link"] = invite_link
                    else:
                        await event.respond(texts.invite_link_warning_text(invite_error, channel_info["link"]))
    else:
        await event.respond(texts.SEND_INPUT_REQUIRED)
        return

    if channel_info:
        try:
            await ChannelManager().add_or_update_channel(
                channel_id=channel_info["id"],
                link=channel_info["link"],
                title=channel_info["title"],
            )

            await set_step(event.sender_id, states.PANEL_STEP)
            await clear_user(event.sender_id)

            await event.respond(
                texts.add_channel_success_text(channel_info),
                buttons=keyboards.channel_detail_buttons(channel_info),
                parse_mode="markdown",
            )
        except Exception as e:
            logger.error(f"Error saving channel: {e}")
            await event.respond(texts.save_channel_error_text(e))
    else:
        error_display = error_msg or "نامشخص"
        await event.respond(texts.channel_not_found_text(error_display))


async def message_handler_edit_channel(event: Message):
    """Handle editing channel link and title"""
    if not event.is_private:
        return

    msg = event.message.text
    step = await get_step(event.sender_id)

    if step == states.LOCK_EDIT_LINK_STEP and msg:
        channel_id = await get_data(event.sender_id, states.LOCK_EDIT_CHANNEL_ID_KEY)
        if channel_id:
            channel_info = await ChannelManager().get_channel(int(channel_id))
            if channel_info:
                title = channel_info.get("title", "")
                await ChannelManager().add_or_update_channel(channel_id=int(channel_id), link=msg, title=title)
                await set_step(event.sender_id, states.PANEL_STEP)
                await clear_user(event.sender_id)

                await event.respond(
                    texts.edit_link_success_text(channel_id, title, msg),
                    buttons=keyboards.channel_detail_buttons({"id": int(channel_id), "title": title, "link": msg}),
                    parse_mode="markdown",
                )
            else:
                await event.respond(texts.EDIT_CHANNEL_INFO_NOT_FOUND)
                await set_step(event.sender_id, states.PANEL_STEP)
                await clear_user(event.sender_id)
        else:
            await event.respond(texts.EDIT_CHANNEL_ID_NOT_FOUND)
            await set_step(event.sender_id, states.PANEL_STEP)
            await clear_user(event.sender_id)

    elif step == states.LOCK_EDIT_TITLE_STEP and msg:
        channel_id = await get_data(event.sender_id, states.LOCK_EDIT_CHANNEL_ID_KEY)
        if channel_id:
            channel_info = await ChannelManager().get_channel(int(channel_id))
            if channel_info:
                link = channel_info.get("link", "")
                await ChannelManager().add_or_update_channel(channel_id=int(channel_id), link=link, title=msg)
                await set_step(event.sender_id, states.PANEL_STEP)
                await clear_user(event.sender_id)

                await event.respond(
                    texts.edit_title_success_text(channel_id, msg, link),
                    buttons=keyboards.channel_detail_buttons({"id": int(channel_id), "title": msg, "link": link}),
                    parse_mode="markdown",
                )
            else:
                await event.respond(texts.EDIT_CHANNEL_INFO_NOT_FOUND)
                await set_step(event.sender_id, states.PANEL_STEP)
                await clear_user(event.sender_id)
        else:
            await event.respond(texts.EDIT_CHANNEL_ID_NOT_FOUND)
            await set_step(event.sender_id, states.PANEL_STEP)
            await clear_user(event.sender_id)


async def message_handler_legacy_channel_lock(event: Message):
    """Legacy text-based channel add/edit flow (Lock_Channels_Menu_Buttons)."""
    msg = (event.message.text or "").strip()
    step = (await get_step(event.sender_id)) or ""

    if msg == states.LEGACY_ADD_CHANNEL_MESSAGE:
        await set_step(event.sender_id, states.LEGACY_ADD_CHANNEL_STEP)
        await Kenzo.send_message(entity=event.sender_id, message=texts.LEGACY_ENTER_CHANNEL_ID)
        raise events.StopPropagation

    if step == states.LEGACY_ADD_CHANNEL_STEP and msg:
        await set_step(event.sender_id, states.LEGACY_WAITING_FOR_LINK_STEP)
        await set_data(event.sender_id, states.LEGACY_WAITING_FOR_ID_KEY, msg)
        await Kenzo.send_message(entity=event.sender_id, message=texts.LEGACY_ENTER_CHANNEL_LINK)
        raise events.StopPropagation

    if step == states.LEGACY_WAITING_FOR_LINK_STEP and msg:
        await set_step(event.sender_id, states.LEGACY_WAITING_FOR_TITLE_STEP)
        await set_data(event.sender_id, states.LEGACY_WAITING_FOR_LINK_KEY, msg)
        await Kenzo.send_message(entity=event.sender_id, message=texts.LEGACY_ENTER_CHANNEL_TITLE)
        raise events.StopPropagation

    if step == states.LEGACY_WAITING_FOR_TITLE_STEP and msg:
        await set_data(event.sender_id, states.LEGACY_WAITING_FOR_TITLE_KEY, msg)
        channel_id = await get_data(event.sender_id, states.LEGACY_WAITING_FOR_ID_KEY)
        channel_link = await get_data(event.sender_id, states.LEGACY_WAITING_FOR_LINK_KEY)
        channel_name = await get_data(event.sender_id, states.LEGACY_WAITING_FOR_TITLE_KEY)
        await set_step(event.sender_id, states.PANEL_STEP)

        await ChannelManager().add_or_update_channel(channel_id=channel_id, link=channel_link, title=channel_name)
        await Kenzo.send_message(
            entity=event.sender_id,
            message=texts.legacy_channel_added_text(channel_id, channel_link, channel_name),
        )
        await clear_user(event.sender_id)
        raise events.StopPropagation

    if step == states.LEGACY_EDIT_CHANNEL_TITLE_STEP and msg:
        await set_data(event.sender_id, states.LEGACY_CHANNEL_NEW_TITLE_KEY, msg)
        await set_step(event.sender_id, states.LEGACY_EDIT_CHANNEL_LINK_STEP)
        await event.respond(texts.LEGACY_ENTER_NEW_LINK)
        raise events.StopPropagation

    if step == states.LEGACY_EDIT_CHANNEL_LINK_STEP and msg:
        ch_id = await get_data(event.sender_id, states.LEGACY_CHANNEL_EDIT_ID_KEY)
        title = await get_data(event.sender_id, states.LEGACY_CHANNEL_NEW_TITLE_KEY)
        await ChannelManager().add_or_update_channel(channel_id=int(ch_id), link=msg, title=title)
        await clear_user(event.sender_id)
        await set_step(event.sender_id, states.PANEL_STEP)
        await event.respond(texts.LEGACY_CHANNEL_UPDATED)
        raise events.StopPropagation


async def handle_chat_action(event: events.ChatAction.Event):
    try:
        bot_me = await Kenzo.get_me()

        if (event.user_kicked or event.user_left) and event.user_id == bot_me.id:
            channel_id = event.chat_id
            channel_manager = ChannelManager()

            existing_channel = await channel_manager.get_channel(channel_id)
            if existing_channel:
                await channel_manager.delete_channel(channel_id)
                logger.info(
                    f"Auto-removed lock channel {channel_id} ({existing_channel.get('title')}) because bot was removed from it"
                )

                for admin_id in ADMIN_ID:
                    try:
                        await Kenzo.send_message(
                            admin_id,
                            texts.auto_removed_channel_text(channel_id, existing_channel),
                            parse_mode="markdown",
                        )
                    except Exception as e:
                        logger.error(f"Could not notify admin {admin_id} about removed channel: {e}")
    except Exception as e:
        logger.error(f"Error in handle_chat_action: {e}")


def register(client):
    client.add_event_handler(
        message_handler_channel_lock,
        events.NewMessage(
            pattern=states.CHANNEL_LOCK_MENU_PATTERN,
            incoming=True,
            from_users=ADMIN_ID,
        ),
    )
    client.add_event_handler(
        message_handler_add_channel,
        events.NewMessage(incoming=True, from_users=ADMIN_ID),
    )
    client.add_event_handler(
        message_handler_edit_channel,
        events.NewMessage(incoming=True, from_users=ADMIN_ID),
    )
    client.add_event_handler(
        message_handler_legacy_channel_lock,
        events.NewMessage(incoming=True, from_users=ADMIN_ID, func=_legacy_channel_lock_message_filter),
    )
    client.add_event_handler(handle_chat_action, events.ChatAction())
