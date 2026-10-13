"""Callback handlers for admin channel_lock."""

from telethon import events

from app.db.crud.channels import ChannelManager
from app.logger import get_logger
from app.telegram.admin.channel_lock import keyboards, states, texts
from app.telegram.keyboards.admin import Panel_Admin_Buttons
from app.telegram.state import set_data, set_step
from config import ADMIN_ID

logger = get_logger(__name__)


def _admin_callback_filter(data: str):
    def _filter(event: events.CallbackQuery.Event) -> bool:
        return event.sender_id in ADMIN_ID and event.data and event.data.decode("UTF-8") == data

    return _filter


def _admin_prefix_callback_filter(prefix: str):
    def _filter(event: events.CallbackQuery.Event) -> bool:
        return event.sender_id in ADMIN_ID and event.data and event.data.decode("UTF-8").startswith(prefix)

    return _filter


async def callback_lock_channels_back(event: events.CallbackQuery.Event):
    """Handle back button - return to admin panel"""
    logger.info("callback_lock_channels_back")

    await set_step(event.sender_id, states.PANEL_STEP)

    username = event.sender.username if event.sender.username else "بدون نام کاربری"
    await event.edit(
        f"**🌺به پنل مدیریت خوش آمدید.**\nایدی عددی شما: `{event.sender_id}`\nنام کاربری شما: @{username}\n",
        buttons=Panel_Admin_Buttons,
    )


async def callback_lock_channels_list(event: events.CallbackQuery.Event):
    """Handle list channels button - show list of locked channels"""
    logger.info("callback_lock_channels_list")

    channel_manager = ChannelManager()
    channels = await channel_manager.get_all_channels()

    if not channels:
        await event.edit(texts.LIST_EMPTY_TEXT, buttons=keyboards.back_to_menu_button())
        return

    message_text = texts.list_text(len(channels))
    await event.edit(message_text, buttons=keyboards.channel_list_buttons(channels))


async def callback_lock_channels_back_to_menu(event: events.CallbackQuery.Event):
    """Handle back to main menu button"""
    logger.info("callback_lock_channels_back_to_menu")

    await set_step(event.sender_id, states.PANEL_STEP)

    channel_manager = ChannelManager()
    channels = await channel_manager.get_all_channels()
    channel_count = len(channels) if channels else 0

    await event.edit(
        texts.main_menu_text(channel_count),
        buttons=keyboards.main_menu_buttons(),
    )


async def callback_lock_channels_back_to_list(event: events.CallbackQuery.Event):
    """Handle back to list button - redirect to list handler"""
    logger.info("callback_lock_channels_back_to_list")
    await callback_lock_channels_list(event)


async def callback_lock_channels_view(event: events.CallbackQuery.Event):
    """Handle view channel details"""
    logger.info("callback_lock_channels_view")

    data = event.data.decode("UTF-8")
    channel_id = int(data.split(":")[1])

    channel_manager = ChannelManager()
    channel_info = await channel_manager.get_channel(channel_id)

    if not channel_info:
        await event.answer(texts.CHANNEL_NOT_FOUND_ALERT, alert=True)
        return

    await event.edit(
        texts.channel_detail_text(channel_info),
        buttons=keyboards.channel_detail_buttons(channel_info),
        parse_mode="markdown",
    )


async def callback_lock_channels_edit_link(event: events.CallbackQuery.Event):
    """Handle edit channel link"""
    logger.info("callback_lock_channels_edit_link")

    data = event.data.decode("UTF-8")
    channel_id = int(data.split(":")[1])

    await set_step(event.sender_id, states.LOCK_EDIT_LINK_STEP)
    await set_data(event.sender_id, states.LOCK_EDIT_CHANNEL_ID_KEY, channel_id)

    await event.edit(
        texts.EDIT_LINK_PROMPT,
        buttons=keyboards.edit_link_back_button(channel_id),
    )


async def callback_lock_channels_edit_title(event: events.CallbackQuery.Event):
    """Handle edit channel title"""
    logger.info("callback_lock_channels_edit_title")

    data = event.data.decode("UTF-8")
    channel_id = int(data.split(":")[1])

    await set_step(event.sender_id, states.LOCK_EDIT_TITLE_STEP)
    await set_data(event.sender_id, states.LOCK_EDIT_CHANNEL_ID_KEY, channel_id)

    await event.edit(
        texts.EDIT_TITLE_PROMPT,
        buttons=keyboards.edit_title_back_button(channel_id),
    )


async def callback_lock_channels_delete(event: events.CallbackQuery.Event):
    """Handle delete channel - show confirmation"""
    logger.info("callback_lock_channels_delete")

    data = event.data.decode("UTF-8")
    channel_id = int(data.split(":")[1])

    channel_manager = ChannelManager()
    channel_info = await channel_manager.get_channel(channel_id)

    if not channel_info:
        await event.answer(texts.CHANNEL_NOT_FOUND_ALERT, alert=True)
        return

    await event.edit(
        texts.delete_confirm_text(channel_info),
        buttons=keyboards.delete_confirm_buttons(channel_id),
        parse_mode="markdown",
    )


async def callback_lock_channels_confirm_delete(event: events.CallbackQuery.Event):
    """Handle confirm delete channel"""
    logger.info("callback_lock_channels_confirm_delete")

    data = event.data.decode("UTF-8")
    channel_id = int(data.split(":")[1])

    channel_manager = ChannelManager()
    channel_info = await channel_manager.get_channel(channel_id)

    if not channel_info:
        await event.answer(texts.CHANNEL_NOT_FOUND_ALERT, alert=True)
        return

    await channel_manager.delete_channel(channel_id)
    await event.answer(texts.DELETE_SUCCESS_ALERT, alert=False)
    await callback_lock_channels_list(event)


async def callback_lock_channels_add(event: events.CallbackQuery.Event):
    """Handle add channel button - show instructions"""
    logger.info("callback_lock_channels_add")

    await set_step(event.sender_id, states.LOCK_ADD_CHANNEL_STEP)
    await event.edit(
        texts.ADD_CHANNEL_INSTRUCTIONS,
        buttons=keyboards.add_channel_back_button(),
    )


def register(client):
    client.add_event_handler(
        callback_lock_channels_back,
        events.CallbackQuery(func=_admin_callback_filter(states.LOCK_CHANNELS_BACK)),
    )
    client.add_event_handler(
        callback_lock_channels_list,
        events.CallbackQuery(func=_admin_callback_filter(states.LOCK_CHANNELS_LIST)),
    )
    client.add_event_handler(
        callback_lock_channels_back_to_menu,
        events.CallbackQuery(func=_admin_callback_filter(states.LOCK_CHANNELS_BACK_TO_MENU)),
    )
    client.add_event_handler(
        callback_lock_channels_back_to_list,
        events.CallbackQuery(func=_admin_callback_filter(states.LOCK_CHANNELS_BACK_TO_LIST)),
    )
    client.add_event_handler(
        callback_lock_channels_view,
        events.CallbackQuery(func=_admin_prefix_callback_filter(states.LOCK_CHANNELS_VIEW_PREFIX)),
    )
    client.add_event_handler(
        callback_lock_channels_edit_link,
        events.CallbackQuery(func=_admin_prefix_callback_filter(states.LOCK_CHANNELS_EDIT_LINK_PREFIX)),
    )
    client.add_event_handler(
        callback_lock_channels_edit_title,
        events.CallbackQuery(func=_admin_prefix_callback_filter(states.LOCK_CHANNELS_EDIT_TITLE_PREFIX)),
    )
    client.add_event_handler(
        callback_lock_channels_delete,
        events.CallbackQuery(func=_admin_prefix_callback_filter(states.LOCK_CHANNELS_DELETE_PREFIX)),
    )
    client.add_event_handler(
        callback_lock_channels_confirm_delete,
        events.CallbackQuery(func=_admin_prefix_callback_filter(states.LOCK_CHANNELS_CONFIRM_DELETE_PREFIX)),
    )
    client.add_event_handler(
        callback_lock_channels_add,
        events.CallbackQuery(func=_admin_callback_filter(states.LOCK_CHANNELS_ADD)),
    )
