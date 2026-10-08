"""Message handlers for user support."""

from telethon import Button, events
from telethon.errors import MessageTooLongError
from telethon.tl.custom import Message

from app import Kenzo
from app.db.crud.keyboards import get_button_text
from app.telegram.keyboards.common import is_keyboard_config_step, is_wizard_step
from app.telegram.keyboards.home import bhome_buttons, home_back_button
from app.telegram.shared.guards.channel_gate import ensure_channel_membership
from app.telegram.shared.utils.maintenance import bot_is_offline
from app.telegram.state import get_step, set_step
from app.utils.text.bot_texts import get_bot_text
from config import ADMIN_ID


async def support_menu_filter(event: Message) -> bool:
    if event.is_channel:
        return False
    if is_wizard_step(await get_step(event.sender_id)):
        return False
    if is_keyboard_config_step(await get_step(event.sender_id)):
        return False
    msg = event.message.text or ""
    support_text = await get_button_text("bt.menu_support", "☎️ پشتیبانی")
    return msg in {support_text, "☎️ پشتیبانی", "/support"}


@bot_is_offline
async def support_menu(event: Message):
    """English docstring for support_menu."""
    if not await ensure_channel_membership(event):
        raise events.StopPropagation

    support_text = await get_bot_text(
        key="support_message",
        default="👈🏻 جهت ارتباط به صورت مستقیم (مشکلات سرویس):\n📍 @AmirKenzoo\n\n🗯 سؤال، پیشنهاد، مشکل و یا انتقاد خودرا در قالب یک پیام متنی واحد به طور کامل ارسال کنید :",
        lang="fa",
    )
    if hasattr(event, "answer"):
        try:
            await event.edit(support_text, buttons=[[home_back_button()]])
        except Exception:
            await event.respond(support_text, buttons=[[home_back_button()]])
    else:
        await event.respond(
            support_text,
            buttons=[Button.text(text="🏠 بازگشت", resize=True, single_use=True)],
        )
    await set_step(event.sender_id, "support")
    raise events.StopPropagation


async def is_support_message(event: Message) -> bool:
    """English docstring for is_support_message."""
    if not event.message.text:
        return False

    user_step = await get_step(event.sender_id)
    if user_step != "support":
        return False

    msg = event.message.text

    commands = (
        "/start",
        "/panel",
        "/support",
        "/help",
        "/buy",
        "/charge",
        "/myconfigs",
        "/mywallet",
        "/games",
        "/dice",
        "/listapps",
    )

    button_texts_list = []
    button_keys = [
        "bt.menu_add_balance",
        "bt.menu_admin_panel",
        "bt.menu_advanced_settings",
        "bt.menu_buy_service",
        "bt.menu_get_trial",
        "bt.menu_help",
        "bt.menu_my_services",
        "bt.menu_profile",
        "bt.menu_support",
        "bt.menu_uptime",
    ]
    defaults = {
        "bt.menu_add_balance": "💰 افزایش موجودی",
        "bt.menu_admin_panel": "⚙️ پنل مدیریت",
        "bt.menu_advanced_settings": "⚙️ تنظیمات پیشرفته",
        "bt.menu_buy_service": "🛍 خرید سرویس",
        "bt.menu_get_trial": "🎁 دریافت تست",
        "bt.menu_help": "📚 راهنما",
        "bt.menu_my_services": "🔑 سرویس های من",
        "bt.menu_profile": "🙍 پروفایل من",
        "bt.menu_support": "☎️ پشتیبانی",
        "bt.menu_uptime": "🔋 وضعیت سرویس ها",
    }
    for key in button_keys:
        button_texts_list.append(await get_button_text(key, defaults.get(key)))
    button_texts = tuple(button_texts_list)

    other_texts = (
        "☎️",
        "🏠",
        "🏠 بازگشت",
        "🛍 خرید سرویس",
        "🔑 سرویس های من",
        "💰 افزایش موجودی",
        "🙍 پروفایل من",
        "📚 راهنما",
        "⚙️ تنظیمات پیشرفته",
        "🔙 بازگشت به پنل",
    )

    if msg.startswith(commands):
        return False

    if msg in button_texts or msg in other_texts:
        return False

    return not msg.startswith(("☎️", "🏠", "/"))


@bot_is_offline
async def support_message(event: Message):
    """English docstring for support_message."""
    msg = event.message.text
    from_id = event.sender_id
    first_name = (await event.get_sender()).first_name

    if not msg or len(msg) > 600:
        await event.reply("⚠️ فقط پیام متنی با طول حداکثر 600 کاراکتر ارسال کنید.")
        return

    try:
        for admins in ADMIN_ID:
            await Kenzo.send_message(
                admins,
                f"🏷 پیام جدید | کاربر <a href='tg://user?id={from_id}'>{first_name}</a>\n\n"
                f"➖ فرستنده(ID): <code>{from_id}</code>\n\n"
                f"📝 متن پیام ارسالی: \n\n{msg}",
                buttons=[
                    [
                        Button.inline("⛔️ مسدود کردن", f"bansup_{from_id}"),
                        Button.inline("📨 پاسخ به کاربر", f"sendm_{from_id}"),
                    ]
                ],
                parse_mode="html",
            )

        await event.reply(
            "💬 پیام شما با موفقیت به پشتیبانی ارسال شد.",
            buttons=await bhome_buttons(event.sender_id, "fa"),
        )
        await set_step(event.sender_id, "home")
        raise events.StopPropagation

    except MessageTooLongError:
        await event.reply("⚠️ پیام شما بیش از حد طولانی است. لطفا پیام کوتاه‌تری ارسال کنید.")


def register(client):
    client.add_event_handler(
        support_menu,
        events.NewMessage(incoming=True, func=support_menu_filter),
    )
    client.add_event_handler(
        support_message,
        events.NewMessage(incoming=True, func=is_support_message),
    )
