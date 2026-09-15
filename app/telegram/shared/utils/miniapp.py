"""Open the mini app from a chat, signed in.

Telegram has two kinds of web-app button and only one of them hands the page a
signed ``initData``. A button on the reply keyboard is a
``keyboardButtonSimpleWebView``, documented as opening the app "without sending
user information", so the mini app cannot tell who pressed it and falls back to
its own phone login. An inline ``keyboardButtonWebView`` does send it.

Inline buttons cannot live on a reply keyboard, so the reply keyboard carries a
plain button and pressing it brings this launcher, which is the inline one. The
launcher message stays in the chat, so later visits are a single tap on it.
"""

from __future__ import annotations

from telethon.errors.rpcerrorlist import ButtonUrlInvalidError
from telethon.tl.types import KeyboardInlineButtonRow, ReplyInlineMarkup

from app.telegram.keyboards.common import styled_webview_button
from config import WEBAPP_URL

MINIAPP_NOT_CONFIGURED = "آدرس مینی‌اپ تنظیم نشده. مقدار `WEBAPP_URL` را در فایل .env تنظیم کن."

MINIAPP_NEEDS_HTTPS = (
    "آدرس مینی‌اپ باید با `https://` شروع شود؛ تلگرام آدرس http را برای وب‌اپ قبول نمی‌کند.\n"
    "یک دامنه با گواهی معتبر بگیر و `WEBAPP_URL` را در فایل .env روی آن بگذار."
)

MINIAPP_REJECTED = "تلگرام این آدرس را نپذیرفت. باید یک دامنه با HTTPS معتبر باشد، نه IP خام و نه گواهی self-signed."


def miniapp_url(*, panel: bool = False) -> str:
    base = WEBAPP_URL.rstrip("/")
    return f"{base}?panel=1" if panel else WEBAPP_URL


def miniapp_ready() -> bool:
    return WEBAPP_URL.startswith("https://")


async def send_miniapp_launcher(event, *, label: str, intro: str, panel: bool = False) -> bool:
    """Reply with an inline web-view button, or explain why there isn't one."""
    if not WEBAPP_URL:
        await event.reply(MINIAPP_NOT_CONFIGURED)
        return False
    if not miniapp_ready():
        await event.reply(MINIAPP_NEEDS_HTTPS)
        return False

    buttons = ReplyInlineMarkup([KeyboardInlineButtonRow([styled_webview_button(label, miniapp_url(panel=panel))])])
    try:
        await event.reply(intro, buttons=buttons)
    except ButtonUrlInvalidError:
        await event.reply(MINIAPP_REJECTED)
        return False
    return True
