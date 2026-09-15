"""Deliver an in-chat menu press to the handler that owns its text.

Menus drawn inside the chat are inline keyboards, so a press arrives as a
callback rather than as the button's own text. Nearly every menu handler in the
bot is registered against a text filter, and there are dozens of them, so rather
than duplicate that routing table this dresses the press up as the message it
would have been and walks the client's own handler list — the same order
Telethon would use, stopping where Telethon would stop.

Nothing here runs unless the glassy keyboard is on; turning it off puts the
reply keyboard back and every press is a real message again.
"""

from __future__ import annotations

import inspect
from types import SimpleNamespace

from telethon import events

from app.logger import get_logger

logger = get_logger(__name__)


class MenuPress:
    """A callback press wearing the shape of the text message handlers read.

    Everything except ``message`` is the real event, so replying, editing and
    identifying the sender behave exactly as they would for a real press.
    """

    def __init__(self, event, text: str):
        self._event = event
        self.message = SimpleNamespace(text=text, message=text, out=False, contact=None, action=None)

    def __getattr__(self, name):
        return getattr(self._event, name)


async def route_text_press(client, event, text: str) -> bool:
    """Hand ``text`` to whichever handlers would have received it as a message."""
    press = MenuPress(event, text)
    delivered = False
    for callback, builder in list(client.list_event_handlers()):
        if not isinstance(builder, events.NewMessage):
            continue
        try:
            matched = builder.filter(press)
            if inspect.isawaitable(matched):
                matched = await matched
        except Exception as exc:
            logger.debug("Menu filter %s refused the press: %s", getattr(callback, "__name__", callback), exc)
            continue
        if not matched:
            continue
        delivered = True
        try:
            await callback(press)
        except events.StopPropagation:
            break
    if not delivered:
        logger.warning("No handler claimed the menu press %r", text)
    return delivered
