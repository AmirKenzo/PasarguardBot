"""Message handler for the admin /webapp test command."""

from telethon import events
from telethon.errors.rpcerrorlist import ButtonUrlInvalidError
from telethon.tl.types import KeyboardInlineButtonRow, ReplyInlineMarkup

from app.telegram.keyboards.common import styled_webview_button
from config import ADMIN_ID, WEBAPP_URL


async def open_webapp(event):
    if not event.is_private:
        return

    if not WEBAPP_URL:
        await event.reply("آدرس وب‌اپ تنظیم نشده. مقدار `WEBAPP_URL` را در فایل .env تنظیم کن.")
        return

    if not WEBAPP_URL.startswith("https://"):
        await event.reply(
            "آدرس وب‌اپ باید حتماً با `https://` شروع شود (تلگرام آدرس http را قبول نمی‌کند).\n"
            "یک دامنه با گواهی SSL معتبر (مثل Let's Encrypt پشت nginx/caddy) پیدا کن و "
            "`WEBAPP_URL` را در فایل .env به آن آدرس تغییر بده."
        )
        return

    buttons = ReplyInlineMarkup([KeyboardInlineButtonRow([styled_webview_button("🧪 باز کردن وب‌اپ", WEBAPP_URL)])])
    try:
        await event.reply("برای تست ورود از سمت تلگرام، روی دکمه زیر بزن:", buttons=buttons)
    except ButtonUrlInvalidError:
        await event.reply(
            "تلگرام این آدرس را نپذیرفت. باید یک دامنه با HTTPS معتبر (نه IP خام و نه گواهی self-signed) باشد."
        )


def register(client):
    client.add_event_handler(
        open_webapp,
        events.NewMessage(pattern=r"/webapp$", incoming=True, from_users=ADMIN_ID),
    )
