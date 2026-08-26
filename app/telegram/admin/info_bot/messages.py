"""Message handlers for admin stats/info bot."""

from telethon import events
from telethon.tl.custom import Message

from app import CustomMarkdown
from app.logger import get_logger
from app.services.telegram.rich_message import send_native_rich_message
from app.telegram.admin.info_bot import keyboards, service
from config import ADMIN_ID

logger = get_logger(__name__)


async def message_handler_infobot(event: Message):
    if not event.is_private:
        return
    payload = await service.main_payload(force=False)
    try:
        blocks = service.main_rich_blocks(payload)
        await send_native_rich_message(event.chat_id, blocks)
    except Exception as rich_exc:
        logger.warning("stats:main rich send failed, falling back: %s", rich_exc)
        msg, entities = CustomMarkdown.parse(service.main_text(payload))
        await event.reply(msg, formatting_entities=entities, buttons=keyboards.main_menu_buttons())


def register(client):
    client.add_event_handler(
        message_handler_infobot,
        events.NewMessage(pattern=r"^👥 آمار گیری$", incoming=True, from_users=ADMIN_ID),
    )
