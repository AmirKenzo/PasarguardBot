"""Admin entry points that open the WebApp."""

from telethon import events
from telethon.tl.custom import Message

from app.telegram.shared.utils.miniapp import send_miniapp_launcher
from config import ADMIN_ID

WEB_PANEL_BUTTON = "🖥 پنل تحت وب"
WEB_PANEL_INTRO = "برای ورود به پنل تحت وب، روی دکمهٔ زیر بزن:"


async def open_webapp(event):
    if not event.is_private:
        return
    await send_miniapp_launcher(event, label="🧪 باز کردن وب‌اپ", intro="برای تست ورود از سمت تلگرام، روی دکمه زیر بزن:")


def _web_panel_filter(event: Message) -> bool:
    if event.sender_id not in ADMIN_ID or not event.is_private:
        return False
    return (event.message.text or "").strip() == WEB_PANEL_BUTTON


async def open_web_panel(event: Message):
    await send_miniapp_launcher(event, label=WEB_PANEL_BUTTON, intro=WEB_PANEL_INTRO, panel=True)
    raise events.StopPropagation


def register(client):
    client.add_event_handler(
        open_webapp,
        events.NewMessage(pattern=r"/webapp$", incoming=True, from_users=ADMIN_ID),
    )
    client.add_event_handler(
        open_web_panel,
        events.NewMessage(incoming=True, func=_web_panel_filter),
    )
