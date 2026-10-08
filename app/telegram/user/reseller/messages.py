"""Message handlers for user reseller flows."""

from telethon import Button, events
from telethon.tl.custom import Message

from app.db.crud.keyboards import get_button_text
from app.db.crud.reseller_accounts import ResellerAccountCRUD
from app.db.crud.settings import SettingsManager
from app.telegram.keyboards.home import home_back_button
from app.telegram.shared.utils.maintenance import bot_is_offline
from app.telegram.state import delete_data, get_step, set_step
from app.telegram.user.reseller import states
from app.telegram.user.reseller.helpers import get_reseller_text, show_reseller_panel_picker
from app.telegram.user.reseller.keyboards import build_my_resellers_list_buttons
from app.telegram.user.reseller.states import RESELLER_FLOW_MSG_KEY


async def _send_my_resellers_list(event: Message) -> None:
    is_callback = hasattr(event, "answer")
    accounts = await ResellerAccountCRUD().get_accounts_by_user(event.sender_id)
    if not accounts:
        settings = await SettingsManager().get_settings()
        buttons = []
        if settings and settings.reseller_sale_mode:
            buttons.append([Button.inline("🏢 خرید پنل نمایندگی", data="ResellerBuy_start")])
        if is_callback:
            buttons.append([home_back_button()])
        text = await get_reseller_text(
            "reseller_my_list_empty",
            "**📋 نمایندگی‌های من**\n\nشما هنوز نمایندگی فعالی ندارید.",
            event.sender_id,
        )
        if is_callback:
            try:
                await event.edit(text, buttons=buttons or None)
                return
            except Exception:
                pass
        await event.respond(text, buttons=buttons or None)
        return

    text = await get_reseller_text(
        "reseller_my_list_intro",
        f"**📋 نمایندگی‌های من** ({len(accounts)} مورد)\n\nیک نمایندگی را انتخاب کنید:",
        event.sender_id,
        count=str(len(accounts)),
    )
    buttons = await build_my_resellers_list_buttons(accounts)
    if is_callback:
        buttons = [*buttons, [home_back_button()]]
        try:
            await event.edit(text, buttons=buttons)
            return
        except Exception:
            pass
    await event.respond(text, buttons=buttons)


@bot_is_offline
async def reseller_menu_message(event: Message):
    if not event.is_private:
        return
    msg = (event.message.text or "").strip()
    buy_text = await get_button_text("bt.menu_buy_reseller", states.RESELLER_MENU_MESSAGE)
    my_text = await get_button_text("bt.menu_my_resellers", states.MY_RESELLERS_MESSAGE)
    settings = await SettingsManager().get_settings()

    if msg == buy_text:
        if not settings or not settings.sale_mode or not settings.reseller_sale_mode:
            await event.respond("⛔️ فروش توسط ادمین بسته است.")
            return
        step = (await get_step(event.sender_id)) or ""
        if step == "panel" or step.startswith("reseller_plan_"):
            await set_step(event.sender_id, "home")
        await delete_data(event.sender_id, RESELLER_FLOW_MSG_KEY)
        await show_reseller_panel_picker(event)
        return

    if msg == my_text:
        await _send_my_resellers_list(event)


async def _reseller_menu_filter(event: Message) -> bool:
    if not event.is_private or not event.message.text:
        return False
    msg = event.message.text.strip()
    buy_text = await get_button_text("bt.menu_buy_reseller", states.RESELLER_MENU_MESSAGE)
    my_text = await get_button_text("bt.menu_my_resellers", states.MY_RESELLERS_MESSAGE)
    return msg in (buy_text, my_text)


def register(client):
    client.add_event_handler(
        reseller_menu_message,
        events.NewMessage(incoming=True, func=_reseller_menu_filter),
    )
