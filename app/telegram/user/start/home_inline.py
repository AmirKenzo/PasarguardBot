"""Callback dispatcher for the home menu when rendered in inline ("glass") mode.

Each home-menu button, when `home_menu_inline_mode` is on, carries callback data
`home.<key>` (see `app.telegram.keyboards.home.bhome_buttons`). Tapping one must land
on the exact same screen a physical reply-keyboard tap would — and, since the whole
point of "glass" mode is a clean inline UI, it should *edit* the tapped message
instead of dropping a new one into the chat wherever that's possible.

Wherever the target screen already has a native CallbackQuery re-entry point (most
of them do — they're used to return from a sub-flow), `_NATIVE_CALLBACK_ACTIONS`
calls it directly with the real event, since those already edit in place. The rest
go through `_HOME_ACTIONS`, reusing the reply-keyboard entry handler; a couple of
those still branch on `event.message.text`/`event.message.message`, so the call is
made through `_TextEventProxy`, which forwards everything else to the real event.
"""

from __future__ import annotations

from types import SimpleNamespace

from telethon import events

from app.db.crud.keyboards import get_button_text
from app.telegram.admin.admin_home.callbacks import callback_back_to_admin_panel
from app.telegram.keyboards.home import bhome_buttons
from app.telegram.shared.utils.maintenance import bot_is_offline
from app.telegram.state import delete_data, get_step, set_step
from app.telegram.user.balance.callbacks import back_to_balance_callback
from app.telegram.user.help.callbacks import callback_back_to_help
from app.telegram.user.profile.callbacks import callback_back_to_profile
from app.telegram.user.reseller.helpers import show_reseller_panel_picker
from app.telegram.user.reseller.messages import _send_my_resellers_list
from app.telegram.user.reseller.states import RESELLER_FLOW_MSG_KEY
from app.telegram.user.services.messages import my_services_handler
from app.telegram.user.settings.messages import advanced_settings_handler
from app.telegram.user.shop.messages import buy_service_handler
from app.telegram.user.start.helpers import fetch_welcome_text, get_user_lang
from app.telegram.user.support.messages import support_menu
from app.telegram.user.trial.messages import free_trial_handler
from config import ADMIN_ID

# key -> (keyboard-button config key, default label, reply-keyboard handler reused as-is)
# `my_services_handler`, `buy_service_handler` and `advanced_settings_handler` already
# check `hasattr(event, "answer")` internally and edit the tapped message when it's set.
_HOME_ACTIONS: dict[str, tuple[str, str, object]] = {
    "services": ("bt.menu_my_services", "🔑 سرویس های من", my_services_handler),
    "trial": ("bt.menu_get_trial", "🎁 دریافت تست", free_trial_handler),
    "buy_service": ("bt.menu_buy_service", "🛍 خرید سرویس", buy_service_handler),
    "support": ("bt.menu_support", "☎️ پشتیبانی", support_menu),
    "advanced_settings": ("bt.menu_advanced_settings", "⚙️ تنظیمات پیشرفته", advanced_settings_handler),
}

# key -> (existing "return to X" CallbackQuery handler, handler already answers the query itself)
_NATIVE_CALLBACK_ACTIONS: dict[str, tuple[object, bool]] = {
    "profile": (callback_back_to_profile, False),
    "add_balance": (back_to_balance_callback, False),
    "help": (callback_back_to_help, False),
    "admin_panel": (callback_back_to_admin_panel, True),
}


# `reseller_menu_message` branches on `isinstance(event, events.CallbackQuery.Event)`
# a few calls deep (to edit the tapped message in place instead of sending a new one),
# which only holds for the *real* event — so these two run against the untouched
# callback event instead of going through `_TextEventProxy`.
async def _open_buy_reseller(event) -> None:
    user_id = event.sender_id
    step = (await get_step(user_id)) or ""
    if step == "panel" or step.startswith("reseller_plan_"):
        await set_step(user_id, "home")
    await delete_data(user_id, RESELLER_FLOW_MSG_KEY)
    await show_reseller_panel_picker(event)


async def _open_my_resellers(event) -> None:
    await _send_my_resellers_list(event)


_RESELLER_ACTIONS: dict[str, object] = {
    "buy_reseller": _open_buy_reseller,
    "my_resellers": _open_my_resellers,
}


class _TextEventProxy:
    """Wraps a CallbackQuery.Event so handlers written for NewMessage still work.

    Every attribute except `message` is forwarded to the real event (sender_id,
    respond, reply, edit, client, get_sender, ...); `message` is a stand-in that
    exposes the resolved button label the way `event.message.text` normally would.
    """

    __slots__ = ("_event", "message")

    def __init__(self, event, text: str):
        self._event = event
        self.message = SimpleNamespace(text=text, message=text)

    def __getattr__(self, name):
        return getattr(self._event, name)


def _home_callback_filter(event: events.CallbackQuery.Event) -> bool:
    return (event.data or b"").startswith(b"home.")


async def _go_home(event: events.CallbackQuery.Event) -> None:
    await set_step(event.sender_id, "home")
    lang = await get_user_lang(event.sender_id)
    welcome_text = await fetch_welcome_text()
    buttons = await bhome_buttons(event.sender_id, lang)
    try:
        await event.edit(welcome_text, buttons=buttons)
    except Exception:
        await event.respond(welcome_text, buttons=buttons)


@bot_is_offline
async def home_menu_callback(event: events.CallbackQuery.Event):
    key = event.data.decode("utf-8").split(".", 1)[1]

    if key == "back":
        await event.answer()
        await _go_home(event)
        return

    if key == "admin_panel" and event.sender_id not in ADMIN_ID:
        await event.answer("⛔️ دسترسی ندارید", alert=True)
        return

    reseller_action = _RESELLER_ACTIONS.get(key)
    if reseller_action is not None:
        await event.answer()
        await reseller_action(event)
        return

    native_action = _NATIVE_CALLBACK_ACTIONS.get(key)
    if native_action is not None:
        handler, self_answers = native_action
        if not self_answers:
            await event.answer()
        await handler(event)
        return

    action = _HOME_ACTIONS.get(key)
    if action is None:
        await event.answer()
        return

    bt_key, default_text, handler = action
    text = await get_button_text(bt_key, default_text)
    await event.answer()
    await handler(_TextEventProxy(event, text))


def register(client):
    client.add_event_handler(
        home_menu_callback,
        events.CallbackQuery(func=_home_callback_filter),
    )
