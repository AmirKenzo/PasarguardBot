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

from telethon import events

from app.logger import get_logger

logger = get_logger(__name__)


class MenuMessage:
    """The message a press stands for, shaped the way readers expect.

    Both Telethon and the bot's own filters reach into the message rather than
    the event: ``NewMessage.filter`` reads ``sender_id``, ``out`` and
    ``fwd_from`` off it before any handler is consulted. A field that is missing
    raises, the filter is skipped, and the handler silently never runs — so the
    fields are spelled out here instead of being supplied on demand.

    Everything a real message can carry but a press cannot — media, a forward
    header, a file — is present and empty, which is the truth about a press.
    """

    def __init__(self, event, text: str):
        self.text = text
        self.raw_text = text
        self.message = text
        self.sender_id = event.sender_id
        self.chat_id = event.chat_id
        self.peer_id = getattr(event, "peer_id", None)
        # The menu card itself: a handler that clears "the message that got us
        # here" should take the menu away, which is what a press looks like.
        self.id = getattr(event, "message_id", None)
        self.out = False
        self.fwd_from = None
        self.forward = None
        self.media = None
        self.photo = None
        self.document = None
        self.file = None
        self.video = None
        self.voice = None
        self.audio = None
        self.sticker = None
        self.contact = None
        self.action = None
        self.entities = None
        self.reply_to = None
        self.reply_to_msg_id = None
        self.reply_markup = None
        self.via_bot_id = None
        self.date = getattr(event, "date", None)

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        # Everything else a real message can carry, a press has not. Falling
        # through answers None, which keeps a filter alive where raising would
        # quietly unregister the handler behind it.


class MenuPress:
    """A callback press wearing the shape of the text message handlers read.

    Everything except ``message`` is the real event, so replying, editing and
    identifying the sender behave exactly as they would for a real press.
    """

    def __init__(self, event, text: str):
        self._event = event
        self.message = MenuMessage(event, text)

    def __getattr__(self, name):
        return getattr(self._event, name)


async def route_text_press(client, event, text: str) -> bool:
    """Hand ``text`` to whichever handlers would have received it as a message."""
    press = MenuPress(event, text)
    delivered = False
    for callback, builder in list(client.list_event_handlers()):
        if not isinstance(builder, events.NewMessage):
            continue
        # A builder that has never seen an update yet refuses every event.
        if not builder.resolved:
            try:
                await builder.resolve(client)
            except Exception as exc:
                logger.warning("Could not resolve a menu handler's filter: %s", exc)
                continue
        try:
            matched = builder.filter(press)
            if inspect.isawaitable(matched):
                matched = await matched
        except Exception as exc:
            # Not routine: a filter only raises here when the press is missing
            # something a real message carries, and that costs us the handler.
            logger.warning(
                "Menu filter %s raised on the press %r: %s",
                getattr(callback, "__name__", callback),
                text,
                exc,
            )
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
