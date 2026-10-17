"""Admin /ping command."""

import time

from telethon import events

from app.telegram.plugins import PluginContext
from config import ADMIN_ID

MODULE_NAME = "admin.ping"
MODULE_ORDER = 10
MODULE_DESCRIPTION = "Admin ping command"


async def ping_pong(event) -> None:
    if not event.is_private:
        return
    started = time.monotonic()
    message = await event.reply("**Pong!**")
    await message.edit(f"**Pong!**\nTook `{time.monotonic() - started:.3f}` seconds")


def setup(ctx: PluginContext) -> None:
    ctx.add_event_handler(ping_pong, events.NewMessage(pattern=r"/ping$", incoming=True, from_users=ADMIN_ID))
