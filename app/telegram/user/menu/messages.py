"""Answer the in-chat home menu.

With the glassy keyboard the home menu is drawn as inline buttons inside the
chat, so a press arrives as a callback instead of as the button's own text. The
menu handlers were written against that text and there are a dozen of them, so
rather than rewrite each one, a press is dressed back up as the message it would
have been and handed to the same handler. Turning the switch off puts the reply
keyboard back and none of this runs.
"""

from __future__ import annotations

from types import SimpleNamespace

from telethon import events

from app.db.crud.keyboards import get_button_text
from app.logger import get_logger
from app.telegram.keyboards.home import HOME_CALLBACK_PREFIX
from app.telegram.keyboards.registry import KEYBOARD_BUTTON_DEFAULTS

logger = get_logger(__name__)

# button key -> the module and handler that already serve it from a text press
MENU_HANDLERS: dict[str, tuple[str, str]] = {
    "bt.menu_my_services": ("app.telegram.user.services.messages", "my_services_handler"),
    "bt.menu_get_trial": ("app.telegram.user.trial.messages", "free_trial_handler"),
    "bt.menu_buy_service": ("app.telegram.user.shop.messages", "buy_service_handler"),
    "bt.menu_profile": ("app.telegram.user.profile.messages", "menu_profile"),
    "bt.menu_add_balance": ("app.telegram.user.balance.messages", "menu_add_balance_handler"),
    "bt.menu_support": ("app.telegram.user.support.messages", "support_menu"),
    "bt.menu_help": ("app.telegram.user.help.messages", "help_menu_handler"),
    "bt.menu_advanced_settings": ("app.telegram.user.settings.messages", "advanced_settings_handler"),
    "bt.menu_my_resellers": ("app.telegram.user.reseller.messages", "reseller_menu_message"),
    "bt.menu_buy_reseller": ("app.telegram.user.reseller.messages", "reseller_menu_message"),
}


class MenuPress:
    """A callback press wearing the shape of the text message handlers read.

    Everything except ``message`` is the real event, so replying, editing and
    identifying the sender all behave exactly as they would for a press on the
    reply keyboard.
    """

    def __init__(self, event, text: str):
        self._event = event
        self.message = SimpleNamespace(text=text, message=text, contact=None, action=None)

    def __getattr__(self, name):
        return getattr(self._event, name)


def _menu_callback_filter(event: events.CallbackQuery.Event) -> bool:
    return event.data.decode("utf-8", "ignore").startswith(HOME_CALLBACK_PREFIX)


async def menu_callback_handler(event: events.CallbackQuery.Event):
    key = event.data.decode("utf-8", "ignore").removeprefix(HOME_CALLBACK_PREFIX)
    await event.answer()

    if key == "bt.menu_admin_panel":
        from config import ADMIN_ID

        if event.sender_id not in ADMIN_ID:
            return
        from app.telegram.admin.admin_home.service import send_admin_home

        sender = await event.get_sender()
        await send_admin_home(event.sender_id, getattr(sender, "username", None))
        raise events.StopPropagation

    target = MENU_HANDLERS.get(key)
    if target is None:
        logger.warning("No handler for home menu key %s", key)
        return

    module_name, attr = target
    module = __import__(module_name, fromlist=[attr])
    label = await get_button_text(key, KEYBOARD_BUTTON_DEFAULTS.get(key, key))
    await getattr(module, attr)(MenuPress(event, label))
    raise events.StopPropagation


def register(client):
    client.add_event_handler(
        menu_callback_handler,
        events.CallbackQuery(func=_menu_callback_filter),
    )
