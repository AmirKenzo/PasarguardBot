"""Message handlers for admin support replies."""

from telethon import events
from telethon.tl.custom import Message

from app import Kenzo
from app.db.crud.user import UserCRUD
from app.telegram.state import delete_data, get_data, get_step, set_step
from config import ADMIN_ID


async def handle_support_reply(event: Message):
    admin_record = await UserCRUD().read_user(event.sender_id)
    if not admin_record or (await get_step(event.sender_id)) != "sendSupport":
        return

    target_id = await get_data(event.sender_id, "idUserSupport")
    if not target_id:
        await event.reply("هیچ کاربری برای پاسخ یافت نشد.")
        await set_step(event.sender_id, "none")
        return

    message_text = event.raw_text or ""

    if message_text in {"🏠", "/start", "/panel"}:
        await delete_data(event.sender_id, "idUserSupport")
        await set_step(event.sender_id, "none")
        await event.reply("ارسال پاسخ لغو شد.")
        return

    try:
        recipient_id = int(target_id)
    except (TypeError, ValueError):
        await event.reply("شناسه کاربر نامعتبر است.")
        await delete_data(event.sender_id, "idUserSupport")
        await set_step(event.sender_id, "none")
        return

    try:
        if not (event.message.media or event.message.message):
            await event.reply("پیام خالی را نمی‌توان ارسال کرد.")
            return

        if event.message.media:
            await Kenzo.send_file(
                recipient_id,
                event.message.media,
                caption=event.message.message or None,
            )
        else:
            await Kenzo.send_message(recipient_id, event.message.message)
        await event.reply("پیام برای کاربر ارسال شد.")
    except Exception as exc:
        await event.reply(f"ارسال پیام به کاربر با خطا مواجه شد: {exc}")


def register(client):
    client.add_event_handler(
        handle_support_reply,
        events.NewMessage(incoming=True, from_users=ADMIN_ID),
    )
