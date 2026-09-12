"""Message handler for the admin /webapp test command."""

from telethon import events
from telethon.tl.types import KeyboardInlineButtonRow, ReplyInlineMarkup

from app.telegram.keyboards.common import styled_webview_button
from config import ADMIN_ID, WEBAPP_URL


async def open_webapp(event):
    if not event.is_private:
        return

    if not WEBAPP_URL:
        await event.reply("آدرس وب‌اپ تنظیم نشده. مقدار `WEBAPP_URL` را در فایل .env تنظیم کن.")
        return

    buttons = ReplyInlineMarkup([KeyboardInlineButtonRow([styled_webview_button("🧪 باز کردن وب‌اپ", WEBAPP_URL)])])
    await event.reply("برای تست ورود از سمت تلگرام، روی دکمه زیر بزن:", buttons=buttons)


def register(client):
    client.add_event_handler(
        open_webapp,
        events.NewMessage(pattern=r"/webapp$", incoming=True, from_users=ADMIN_ID),
    )
