"""Admin side of support: reply to a user, ban and unban from a ticket."""

from __future__ import annotations

from dataclasses import dataclass

from telethon import Button, events
from telethon.tl.custom import Message

from app import Kenzo
from app.db.crud.user import UserCRUD, clear_user_status, set_user_status
from app.telegram.keyboards.admin import Home_Back
from app.telegram.plugins import PluginContext
from app.telegram.state import delete_data, get_data, get_step, set_data, set_step
from config import ADMIN_ID

MODULE_NAME = "admin.support"
MODULE_DESCRIPTION = "Admin support reply flow"

REPLY_STEP = "sendSupport"
TARGET_KEY = "idUserSupport"
CANCEL_TEXTS = frozenset({"🏠", "/start", "/panel"})


@dataclass(frozen=True)
class BanAction:
    ban: bool
    edit: bool
    next_action: str


BAN_ACTIONS: dict[str, BanAction] = {
    "bansup": BanAction(ban=True, edit=False, next_action="unbanunbansup"),
    "unbansup": BanAction(ban=False, edit=False, next_action="banbansup"),
    "unbanunbansup": BanAction(ban=False, edit=True, next_action="banbansup"),
    "banbansup": BanAction(ban=True, edit=True, next_action="unbansup"),
}
CALLBACK_PREFIXES = ("sendm_", *(f"{name}_" for name in BAN_ACTIONS))


def _callback_filter(event: events.CallbackQuery.Event) -> bool:
    return event.sender_id in ADMIN_ID and event.data.decode().startswith(CALLBACK_PREFIXES)


async def support_callback(event: events.CallbackQuery.Event) -> None:
    name, _, user_id = event.data.decode().rpartition("_")

    if name == "sendm":
        await event.respond(f"پیام خود را به کاربر ( {user_id} ) ارسال کنید:", buttons=Home_Back)
        await set_step(event.sender_id, REPLY_STEP)
        await set_data(event.sender_id, TARGET_KEY, user_id)
        return

    action = BAN_ACTIONS[name]
    target = int(user_id)
    try:
        if action.ban:
            await event.answer("⛔️ کاربر مسدود شد.", alert=True)
            await set_user_status(target, "ban")
        else:
            await event.answer(" کاربر ✅ رفع مسدودی شد.", alert=True)
            await clear_user_status(target)
        toggle_label = "✅ رفع مسدودی" if action.ban else "🚫 مسدود کردن"
        show = event.edit if action.edit else event.respond
        await show(
            f"🔒 کاربر <a href='tg://user?id={target}'>{target}</a> {'بن شد' if action.ban else 'ان بن شد'}.",
            parse_mode="html",
            buttons=[
                Button.inline("📨 ارسال پاسخ", f"sendm_{target}"),
                Button.inline(toggle_label, f"{action.next_action}_{target}"),
            ],
        )
    except Exception as exc:
        await event.answer(f"خطا در بن کردن کاربر: {exc!s}", alert=True)


async def _end_reply(event: Message, notice: str) -> None:
    await delete_data(event.sender_id, TARGET_KEY)
    await set_step(event.sender_id, "none")
    await event.reply(notice)


async def support_reply(event: Message) -> None:
    if not await UserCRUD().read_user(event.sender_id) or await get_step(event.sender_id) != REPLY_STEP:
        return

    target_id = await get_data(event.sender_id, TARGET_KEY)
    if not target_id:
        await event.reply("هیچ کاربری برای پاسخ یافت نشد.")
        await set_step(event.sender_id, "none")
        return
    if (event.raw_text or "") in CANCEL_TEXTS:
        await _end_reply(event, "ارسال پاسخ لغو شد.")
        return
    try:
        recipient_id = int(target_id)
    except TypeError, ValueError:
        await _end_reply(event, "شناسه کاربر نامعتبر است.")
        return

    message = event.message
    if not (message.media or message.message):
        await event.reply("پیام خالی را نمی‌توان ارسال کرد.")
        return
    try:
        if message.media:
            await Kenzo.send_file(recipient_id, message.media, caption=message.message or None)
        else:
            await Kenzo.send_message(recipient_id, message.message)
        await event.reply("پیام برای کاربر ارسال شد.")
    except Exception as exc:
        await event.reply(f"ارسال پیام به کاربر با خطا مواجه شد: {exc}")


def setup(ctx: PluginContext) -> None:
    ctx.add_event_handler(support_reply, events.NewMessage(incoming=True, from_users=ADMIN_ID))
    ctx.add_event_handler(support_callback, events.CallbackQuery(func=_callback_filter))
