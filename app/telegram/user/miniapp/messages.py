"""The home button that opens the mini app."""

from __future__ import annotations

from telethon import events
from telethon.tl.custom import Message

from app.db.crud.keyboards import KeyboardButtonCRUD, get_button_text
from app.db.crud.settings import SettingsManager
from app.telegram.keyboards.common import _get_keyboard_button_config
from app.telegram.keyboards.home import MINIAPP_MODE_OFF, miniapp_mode
from app.telegram.shared.utils.maintenance import bot_is_offline
from app.telegram.shared.utils.miniapp import send_miniapp_launcher
from app.utils.text.bot_texts import get_bot_text
from app.utils.text.glass import unglass_text

DEFAULT_MINIAPP_BUTTON = "🚀 ورود به اپلیکیشن"
MINIAPP_OPEN_LABEL = "🚀 باز کردن اپلیکیشن"
MINIAPP_INTRO = "برای ورود، دکمهٔ زیر را بزن. همین پیام در چت می‌ماند، پس دفعهٔ بعد یک کلیک کافی است."


async def _miniapp_button_filter(event: Message) -> bool:
    if not event.is_private or event.is_channel:
        return False
    setting = await SettingsManager().get_settings()
    if miniapp_mode(setting) == MINIAPP_MODE_OFF:
        return False
    msg = unglass_text((event.message.text or "").strip())
    label = unglass_text(await get_button_text("bt.menu_miniapp", DEFAULT_MINIAPP_BUTTON))
    return msg in {label, DEFAULT_MINIAPP_BUTTON}


@bot_is_offline
async def miniapp_button_handler(event: Message):
    label, style = await _get_keyboard_button_config(
        KeyboardButtonCRUD(), "bt.menu_miniapp_open", MINIAPP_OPEN_LABEL, default_style="primary"
    )
    intro = await get_bot_text(key="miniapp_launcher_message", default=MINIAPP_INTRO, lang="fa")
    await send_miniapp_launcher(event, label=label, intro=intro, style=style)
    raise events.StopPropagation


def register(client):
    client.add_event_handler(
        miniapp_button_handler,
        events.NewMessage(incoming=True, func=_miniapp_button_filter),
    )
