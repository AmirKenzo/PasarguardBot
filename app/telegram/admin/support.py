"""Admin side of support: reply to a user, refresh a ticket's service, ban/unban."""

from __future__ import annotations

from dataclasses import dataclass, replace

from telethon import Button, events
from telethon.errors.rpcerrorlist import MessageNotModifiedError
from telethon.tl.custom import Message

from app import Kenzo
from app.db.crud.user import UserCRUD, clear_user_status, set_user_status
from app.logger import get_logger
from app.services.telegram.rich_message import edit_native_rich_message
from app.telegram.keyboards.admin import Home_Back
from app.telegram.plugins import PluginContext
from app.telegram.shared.support_ticket import (
    FILTER_ACTIVE,
    FILTER_ALL,
    TARGET_GENERAL,
    ServicesListContext,
    build_admin_service_detail,
    build_admin_service_detail_rich,
    build_admin_services_list,
    build_ticket_view,
    mint_list_context,
    mint_token,
    recall_list_context,
    recall_ticket,
    remember_list_context,
    remember_ticket,
    ticket_from_message_text,
)
from app.telegram.state import delete_data, get_data, get_step, set_data, set_step
from config import ADMIN_ID

logger = get_logger(__name__)

MODULE_NAME = "admin.support"
MODULE_DESCRIPTION = "Admin support reply flow"

REPLY_STEP = "sendSupport"
TARGET_KEY = "idUserSupport"
CANCEL_TEXTS = frozenset({"🏠", "/start", "/panel"})

REFRESH_PREFIX = "supref:"
OTHER_SERVICES_PREFIX = "supoth:"
LIST_PREFIX = "supl:"
DETAIL_PREFIX = "supd:"
BACK_PREFIX = "supb:"


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
CALLBACK_PREFIXES = (
    "sendm_",
    REFRESH_PREFIX,
    OTHER_SERVICES_PREFIX,
    LIST_PREFIX,
    DETAIL_PREFIX,
    BACK_PREFIX,
    *(f"{name}_" for name in BAN_ACTIONS),
)


def _callback_filter(event: events.CallbackQuery.Event) -> bool:
    return event.sender_id in ADMIN_ID and event.data.decode().startswith(CALLBACK_PREFIXES)


async def _refresh_ticket(event: events.CallbackQueryEvent | events.CallbackQuery.Event, data: str) -> None:
    """Re-read the service and rewrite the ticket message itself."""
    parts = data.split(":")
    if len(parts) < 3:
        await event.answer("درخواست نامعتبر است.", alert=True)
        return
    _, raw_user_id, target = parts[:3]
    token = parts[3] if len(parts) > 3 else ""
    try:
        user_id = int(raw_user_id)
    except ValueError:
        await event.answer("درخواست نامعتبر است.", alert=True)
        return

    ticket = await recall_ticket(token)
    if ticket is not None and int(ticket.user_id) != user_id:
        ticket = None
    if ticket is None:
        # The cache entry is gone (or the button predates it): rebuild the ticket
        # from the message itself so the original message can still be updated.
        try:
            message = await event.get_message()
        except Exception:
            message = None
        ticket = ticket_from_message_text(getattr(message, "message", "") or "", user_id, target)
        logger.info("support refresh: cache miss uid=%s target=%s recovered=%s", user_id, target, ticket is not None)

    if ticket is None or not ticket.text:
        await event.answer("⚠️ متن این تیکت پیدا نشد؛ لطفاً از کاربر بخواهید دوباره پیام بدهد.", alert=True)
        return
    if not ticket.token:
        ticket = replace(ticket, token=mint_token())

    text, buttons = await build_ticket_view(ticket)
    try:
        await event.edit(text, buttons=buttons, parse_mode="html", link_preview=False)
    except MessageNotModifiedError:
        await event.answer("اطلاعات از قبل به‌روز است.")
        await remember_ticket(ticket)
        return
    except Exception as exc:
        logger.warning("support refresh: edit failed for %s: %s", user_id, exc)
        await event.answer("⚠️ ویرایش پیام ناموفق بود؛ کمی بعد دوباره تلاش کنید.", alert=True)
        return
    await remember_ticket(ticket)
    await event.answer("🔄 اطلاعات به‌روزرسانی شد.")


async def _safe_rich_detail(context_token: str, context: ServicesListContext, code: int):
    try:
        return await build_admin_service_detail_rich(context_token, context, code)
    except Exception as exc:
        logger.warning("support detail: rich build failed for %s: %s", context.user_id, exc)
        return None


async def _safe_list(context_token: str, context: ServicesListContext):
    try:
        return await build_admin_services_list(context_token, context)
    except Exception as exc:
        logger.warning("support list: build failed for %s: %s", context.user_id, exc)
        return None, None


async def _send_services_list(
    event: events.CallbackQuery.Event, context_token: str, context: ServicesListContext
) -> None:
    """The list stays a normal message with an inline keyboard."""
    text, buttons = await _safe_list(context_token, context)
    if text is None:
        await event.respond("❌ دریافت لیست سرویس‌های این کاربر ناموفق بود.")
        return
    await event.respond(text, buttons=buttons, parse_mode="html", link_preview=False)


async def _edit_services_list(
    event: events.CallbackQuery.Event, context_token: str, context: ServicesListContext
) -> None:
    text, buttons = await _safe_list(context_token, context)
    if text is None:
        return
    try:
        await event.edit(text, buttons=buttons, parse_mode="html", link_preview=False)
    except Exception as exc:
        # Includes rich -> plain edits: keep the list reachable even if the edit is
        # rejected, by sending it as a new message.
        logger.warning("support list: edit failed for %s: %s", context.user_id, exc)
        try:
            await event.respond(text, buttons=buttons, parse_mode="html", link_preview=False)
        except Exception as respond_exc:
            logger.warning("support list: resend failed for %s: %s", context.user_id, respond_exc)


async def _edit_service_detail(
    event: events.CallbackQuery.Event, context_token: str, context: ServicesListContext, code: int
) -> None:
    blocks = await _safe_rich_detail(context_token, context, code)
    if blocks is not None:
        try:
            await edit_native_rich_message(event, blocks)
            return
        except Exception as exc:
            logger.warning("support detail: rich edit failed (%s); using inline keyboard", exc)

    text, buttons = await build_admin_service_detail(context_token, context, code)
    try:
        await event.edit(text, buttons=buttons, parse_mode="html", link_preview=False)
    except Exception as exc:
        logger.warning("support detail: edit failed for %s: %s", context.user_id, exc)


async def _open_services_list(event: events.CallbackQuery.Event, data: str) -> None:
    """``supoth:<user>:0:<target>[:token]`` opens the list as a new message."""
    parts = data.split(":")
    if len(parts) < 4:
        await event.answer("درخواست نامعتبر است.", alert=True)
        return
    _, raw_user_id, _page, target = parts[:4]
    token = parts[4] if len(parts) > 4 else ""
    try:
        user_id = int(raw_user_id)
    except ValueError:
        await event.answer("درخواست نامعتبر است.", alert=True)
        return

    await event.answer()
    ticket = await recall_ticket(token)
    sender_name = ticket.sender_name if ticket is not None and int(ticket.user_id) == user_id else None
    context = ServicesListContext(user_id=user_id, target=target or TARGET_GENERAL, sender_name=sender_name)
    context_token = mint_list_context()
    await remember_list_context(context_token, context)
    await _send_services_list(event, context_token, context)


async def _edit_services_page(event: events.CallbackQuery.Event, data: str) -> None:
    """``supl:<ctx>:<filter>:<page>`` — filter and page inside the same message."""
    parts = data.split(":")
    if len(parts) != 4:
        await event.answer("درخواست نامعتبر است.", alert=True)
        return
    _, context_token, filter_value, raw_page = parts
    if filter_value not in (FILTER_ALL, FILTER_ACTIVE):
        await event.answer("درخواست نامعتبر است.", alert=True)
        return
    try:
        page = int(raw_page)
    except ValueError:
        page = 1

    context = await recall_list_context(context_token)
    if context is None:
        await event.answer("⚠️ این صفحه منقضی شده است؛ دوباره از تیکت باز کنید.", alert=True)
        return

    await event.answer()
    context = replace(context, filter=filter_value, page=page)
    await remember_list_context(context_token, context)
    await _edit_services_list(event, context_token, context)


async def _open_service_detail(event: events.CallbackQuery.Event, data: str) -> None:
    """``supd:<ctx>:<code>`` — one service's facts with a back button."""
    parts = data.split(":")
    if len(parts) != 3:
        await event.answer("درخواست نامعتبر است.", alert=True)
        return
    _, context_token, raw_code = parts
    context = await recall_list_context(context_token)
    if context is None:
        await event.answer("⚠️ این صفحه منقضی شده است؛ دوباره از تیکت باز کنید.", alert=True)
        return
    try:
        code = int(raw_code)
    except ValueError:
        await event.answer("درخواست نامعتبر است.", alert=True)
        return

    await event.answer()
    await _edit_service_detail(event, context_token, context, code)


async def _back_to_services_list(event: events.CallbackQuery.Event, data: str) -> None:
    """``supb:<ctx>`` — return to the list with the filter and page it had."""
    _, _, context_token = data.partition(":")
    context = await recall_list_context(context_token)
    if context is None:
        await event.answer("⚠️ این صفحه منقضی شده است؛ دوباره از تیکت باز کنید.", alert=True)
        return
    await event.answer()
    await _edit_services_list(event, context_token, context)


async def support_callback(event: events.CallbackQuery.Event) -> None:
    data = event.data.decode("utf-8", "ignore")

    if data.startswith(REFRESH_PREFIX):
        await _refresh_ticket(event, data)
        return
    if data.startswith(OTHER_SERVICES_PREFIX):
        await _open_services_list(event, data)
        return
    if data.startswith(LIST_PREFIX):
        await _edit_services_page(event, data)
        return
    if data.startswith(DETAIL_PREFIX):
        await _open_service_detail(event, data)
        return
    if data.startswith(BACK_PREFIX):
        await _back_to_services_list(event, data)
        return

    name, _, user_id = data.rpartition("_")

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


def setup(kenzo: PluginContext) -> None:
    kenzo.add_event_handler(support_reply, events.NewMessage(incoming=True, from_users=ADMIN_ID))
    kenzo.add_event_handler(support_callback, events.CallbackQuery(func=_callback_filter))
