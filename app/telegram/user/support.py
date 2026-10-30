"""User support: pick the related service, show its state, then relay the message.

The user should never have to describe a service the bot already knows about. The
flow therefore asks which service a message is about (all of them, or "general"),
shows the live state of that service with the matching action — renew, buy volume,
or just send the message — and only then takes the text. A panel problem never
blocks the message: the screen and the admin ticket both say the data was not
available.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any

from telethon import events
from telethon.errors.rpcerrorlist import MessageNotModifiedError
from telethon.tl.custom import Message

from app.db.crud.keyboards import get_button_text
from app.db.crud.panels import PanelsManager
from app.db.crud.services import ServiceCRUD, get_user_services_paginated
from app.logger import get_logger
from app.services.support import (
    PANEL_ERROR_UNREACHABLE,
    STATE_ACTIVE,
    STATE_DISABLED,
    STATE_EXPIRED,
    STATE_EXPIRED_LIMITED,
    STATE_LIMITED,
    STATE_ON_HOLD,
    STATE_UNKNOWN,
    ServiceSnapshot,
    build_service_card,
    build_service_snapshot,
    card_state_text,
    load_service_snapshot,
    load_service_states,
    load_services_overview,
    panel_error_text,
    service_belongs_to,
    service_warnings,
    state_label,
    state_style,
)
from app.telegram.keyboards.common import (
    build_telegram_button_style,
    is_keyboard_config_step,
    is_wizard_step,
    styled_callback_button,
)
from app.telegram.keyboards.home import bhome_buttons, home_back_button
from app.telegram.plugins import PluginContext
from app.telegram.shared.guards.channel_gate import ensure_channel_membership
from app.telegram.shared.support_ticket import (
    TARGET_ALL,
    TARGET_GENERAL,
    SupportTicket,
    mint_token,
    send_ticket_to_admins,
)
from app.telegram.shared.utils.maintenance import bot_is_offline
from app.telegram.state import delete_data, get_data, get_step, set_data, set_step
from app.utils.formatting.dates import relative_time, timestamp_to_persian_expiry
from app.utils.formatting.traffic import format_size
from app.utils.text.bot_texts import get_bot_text
from app.utils.text.default_texts import DEFAULT_BOT_TEXTS

logger = get_logger(__name__)

MODULE_NAME = "user.support"
MODULE_REQUIRED = True
MODULE_DESCRIPTION = "User support messaging flow"

SUPPORT_STEP = "support"
PICK_STEP = "support_pick"
STATUS_STEP = "support_status"
ALL_STEP = "support_all"
SUPPORT_STEPS = frozenset({SUPPORT_STEP, PICK_STEP, STATUS_STEP, ALL_STEP})

TARGET_KEY = "support_target"
ORIGIN_KEY = "support_origin"

ORIGIN_MENU = "menu"
ORIGIN_PICKER = "picker"
ORIGIN_SERVICE = "service"

SERVICES_PER_PAGE = 6
MAX_MESSAGE_LENGTH = 600

CB_PICK = "sup:pick:"
CB_SERVICE = "sup:svc:"
CB_CONTINUE = "sup:cont:"
CB_REPORT = "sup:report:"
CB_ALL = "sup:all"
CB_GENERAL = "sup:general"
CB_BACK = "sup:back"
CB_PREFIXES = (CB_PICK, CB_SERVICE, CB_CONTINUE, CB_REPORT)


# --------------------------------------------------------------------------- #
#  Entry points                                                                #
# --------------------------------------------------------------------------- #


async def support_menu_filter(event: Message) -> bool:
    if event.is_channel:
        return False
    step = await get_step(event.sender_id)
    if is_wizard_step(step) or is_keyboard_config_step(step):
        return False
    msg = event.message.text or ""
    support_text = await get_button_text("bt.menu_support", "☎️ پشتیبانی")
    return msg in {support_text, "☎️ پشتیبانی", "/support"}


@bot_is_offline
async def support_menu(event: Message):
    """Open support: one service is selected for you, several ask you to pick."""
    if not await ensure_channel_membership(event):
        raise events.StopPropagation
    await _show_entry(event)
    raise events.StopPropagation


async def _is_reserved_text(msg: str) -> bool:
    """Menu labels and commands that must never be taken as support text."""
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
    button_texts = [await get_button_text(key, defaults[key]) for key in button_keys]

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
        return True
    if msg in button_texts or msg in other_texts:
        return True
    return msg.startswith(("☎️", "🏠", "/"))


async def is_support_message(event: Message) -> bool:
    """Text goes to support only after the user asked to write one.

    The picker and the status screens are navigation: typing there must not file a
    ticket, so only the ``support`` step (the "write your message" prompt) accepts
    text. The other steps answer with a hint instead.
    """
    if not event.message.text:
        return False
    if await get_step(event.sender_id) != SUPPORT_STEP:
        return False
    return not await _is_reserved_text(event.message.text)


async def is_pending_support_text(event: Message) -> bool:
    """Text typed on a support screen that still waits for a button press."""
    if not event.message.text:
        return False
    if await get_step(event.sender_id) not in (PICK_STEP, STATUS_STEP, ALL_STEP):
        return False
    return not await _is_reserved_text(event.message.text)


SUPPORT_SCREEN_HINTS = {
    PICK_STEP: "برای ثبت گزارش اول یک سرویس را انتخاب کن یا دکمهٔ «☎️ موضوع عمومی / نمی‌دانم» را بزن.",
    STATUS_STEP: "برای ارسال گزارش، دکمهٔ «📨 هنوز نیاز به پشتیبانی دارم» را بزن.",
    ALL_STEP: "برای ارسال گزارش، دکمهٔ «📨 ادامه و ارسال پیام» را بزن.",
}


@bot_is_offline
async def support_screen_text(event: Message):
    """Explain the next step instead of silently filing the text as a ticket."""
    step = await get_step(event.sender_id)
    hint = SUPPORT_SCREEN_HINTS.get(step or "", "برای ارسال گزارش از دکمه‌های همین صفحه استفاده کن.")
    await event.reply(hint)
    raise events.StopPropagation


@bot_is_offline
async def support_message(event: Message):
    """Relay one text message to every admin, with the selected service attached."""
    msg = event.message.text
    user_id = event.sender_id

    if not msg or len(msg) > MAX_MESSAGE_LENGTH:
        await event.reply("⚠️ فقط پیام متنی با طول حداکثر 600 کاراکتر ارسال کنید.")
        return

    target, service = await _normalized_target(user_id, await get_data(user_id, TARGET_KEY))
    sender = await _safe_sender(event)
    ticket = SupportTicket(
        user_id=user_id,
        target=target,
        text=msg,
        sender_name=_display_name(sender),
        sender_username=(getattr(sender, "username", None) or None),
        created_at=int(datetime.now(UTC).timestamp()),
        token=mint_token(),
    )

    delivered = await send_ticket_to_admins(ticket)
    if not delivered:
        await event.reply("⚠️ ارسال پیام به پشتیبانی ناموفق بود. لطفاً دوباره تلاش کنید.")
        return

    await event.reply(
        f"💬 پیام شما با موفقیت به پشتیبانی ارسال شد.\n🧾 سرویس مرتبط: {_target_context_text(target, service)}",
        buttons=await bhome_buttons(user_id, "fa"),
    )
    await delete_data(user_id, TARGET_KEY)
    await delete_data(user_id, ORIGIN_KEY)
    await set_step(user_id, "home")
    raise events.StopPropagation


# --------------------------------------------------------------------------- #
#  Screens                                                                     #
# --------------------------------------------------------------------------- #


async def _show_entry(event) -> None:
    services = await _user_services(event.sender_id)
    if not services:
        await _show_no_service_prompt(event)
        return
    if len(services) == 1:
        await _render_service_status(event, services[0], services_total=1, origin=ORIGIN_MENU)
        return
    await _render_picker(event, 1, services=services)


async def _show_no_service_prompt(event) -> None:
    text = (
        f"{await _support_text()}\n\n"
        "📋 در حال حاضر سرویسی برای شما ثبت نشده است؛ اما می‌توانید همین حالا "
        "پیام عمومی پشتیبانی را بفرستید."
    )
    await set_data(event.sender_id, TARGET_KEY, TARGET_GENERAL)
    await set_step(event.sender_id, SUPPORT_STEP)
    await _render(event, text, [[home_back_button()]])


async def _render_picker(event, page: int, *, services: list[Any] | None = None) -> None:
    user_id = event.sender_id
    services = services if services is not None else await _user_services(user_id)
    if not services:
        await _show_no_service_prompt(event)
        return
    if len(services) == 1:
        await _render_service_status(event, services[0], services_total=1, origin=ORIGIN_MENU)
        return

    panels_by_code = {panel.code: panel for panel in await PanelsManager().get_all_panels()}
    total = len(services)
    pages = max(1, math.ceil(total / SERVICES_PER_PAGE))
    page = min(max(1, page), pages)
    start = (page - 1) * SERVICES_PER_PAGE
    chunk = services[start : start + SERVICES_PER_PAGE]

    # Best effort: one panel read per visible row so the button can say "volume
    # exhausted" or "disabled"; a panel outage falls back to the stored status.
    try:
        cards = await load_service_states(chunk, panels_by_code=panels_by_code)
    except Exception as exc:
        logger.warning("support: live picker states failed, using stored ones: %s", exc)
        cards = [build_service_card(service, panels_by_code.get(service.in_panel)) for service in chunk]

    rows = []
    for card in cards:
        rows.append([_button(_picker_label(card), f"{CB_SERVICE}{card.code}", state_style(card.state))])

    navigation = []
    if page > 1:
        navigation.append(_button("◀️ صفحه قبل", f"{CB_PICK}{page - 1}"))
    if page < pages:
        navigation.append(_button("صفحه بعد ▶️", f"{CB_PICK}{page + 1}"))
    if navigation:
        rows.append(navigation)
    rows.append([_button("📋 همهٔ سرویس‌ها", CB_ALL), _button("☎️ موضوع عمومی / نمی‌دانم", CB_GENERAL)])
    rows.append([home_back_button()])

    text = (
        "☎️ **پشتیبانی**\n\n"
        f"📋 **تعداد سرویس‌های شما:** {total}\n"
        f"📄 **صفحه:** {page} از {pages}\n\n"
        "برای اینکه سریع‌تر کمکت کنیم، سرویس مرتبط با مشکلت را انتخاب کن یا "
        "یکی از گزینه‌های پایین را بزن:"
    )
    await set_data(user_id, TARGET_KEY, TARGET_GENERAL)
    await set_step(user_id, PICK_STEP)
    await _render(event, text, rows)


async def _render_service_status(event, service: Any, *, services_total: int, origin: str | None = None) -> None:
    user_id = event.sender_id
    try:
        snapshot = await load_service_snapshot(service)
    except Exception as exc:  # the status screen must still render
        logger.warning("support: status load failed for service %s: %s", getattr(service, "code", "?"), exc)
        snapshot = build_service_snapshot(service, None, None, panel_error=PANEL_ERROR_UNREACHABLE)

    if origin is not None:
        await set_data(user_id, ORIGIN_KEY, origin)
    else:
        origin = await get_data(user_id, ORIGIN_KEY) or ORIGIN_MENU

    await set_data(user_id, TARGET_KEY, str(snapshot.code))
    await set_step(user_id, STATUS_STEP)
    back_data = _status_back_data(snapshot.code, services_total, origin)
    await _render(event, _status_text(snapshot), _status_buttons(snapshot, back_data=back_data))


async def _render_all(event) -> None:
    user_id = event.sender_id
    overview = await load_services_overview(user_id)
    if not overview.total:
        await _show_no_service_prompt(event)
        return

    await set_data(user_id, TARGET_KEY, TARGET_ALL)
    await set_step(user_id, ALL_STEP)

    text = (
        "📋 **همهٔ سرویس‌های شما**\n\n"
        f"🧾 تعداد کل: **{overview.total}**\n"
        f"🟢 فعال: **{overview.count(STATE_ACTIVE)}**\n"
        f"🔴 منقضی: **{overview.count(STATE_EXPIRED)}**\n"
        f"⚪️ نامشخص: **{overview.count(STATE_UNKNOWN)}**"
    )
    if overview.expiring_soon:
        text += f"\n🟡 نزدیک انقضا: **{overview.expiring_soon}**"
    text += (
        "\n\n📌 این خلاصه بر اساس اطلاعات ثبت‌شده در ربات است و وضعیت لحظه‌ای پنل را شامل نمی‌شود."
        "\n📌 با ادامه، همین خلاصه همراه پیام شما برای پشتیبانی ارسال می‌شود."
    )

    back_data = f"{CB_PICK}1" if overview.total > 1 else "home.back"
    rows = [
        [_button("📨 ادامه و ارسال پیام", f"{CB_CONTINUE}{TARGET_ALL}", "primary")],
        [_button("☎️ موضوع عمومی / نمی‌دانم", CB_GENERAL), _button("🔙 بازگشت", back_data)],
    ]
    await _render(event, text, rows)


async def _show_message_prompt(event, target: str) -> None:
    user_id = event.sender_id
    target, service = await _normalized_target(user_id, target)
    text = (
        f"{await _support_text()}\n\n"
        f"🧾 **سرویس مرتبط:** {_target_context_text(target, service)}\n"
        "📝 پیام خود را در **یک پیام متنی** (حداکثر ۶۰۰ کاراکتر) بفرستید."
    )
    await set_data(user_id, TARGET_KEY, target)
    await set_step(user_id, SUPPORT_STEP)
    await _render(event, text, [[_button("🔙 بازگشت", CB_BACK)]])


async def _go_back(event) -> None:
    user_id = event.sender_id
    target = await get_data(user_id, TARGET_KEY)
    if target == TARGET_ALL:
        await _render_all(event)
        return
    if target and str(target).isdigit():
        service = await _owned_service(user_id, target)
        if service is not None:
            await _render_service_status(event, service, services_total=await _count_services(user_id), origin=None)
            return
    await _show_entry(event)


# --------------------------------------------------------------------------- #
#  Status text and buttons                                                     #
# --------------------------------------------------------------------------- #


def _status_text(snapshot: ServiceSnapshot) -> str:
    lines = [
        "🛠 **وضعیت سرویس انتخابی**",
        "",
        f"🔷 **نام کانفیگ:** `{snapshot.config_name}`",
        f"#️⃣ **کد سرویس:** `{snapshot.code}`",
        f"🌐 **پنل:** {snapshot.panel_name}",
        "",
        f"🎛 **وضعیت:** {state_label(snapshot.state)}",
    ]
    if snapshot.is_test:
        lines.append("🧪 **نوع سرویس:** تست (قابل تمدید یا خرید حجم نیست)")

    if snapshot.panel_available:
        lines.extend(_live_lines(snapshot))
        lines.extend(_state_lines(snapshot))
    else:
        lines.append(f"⚠️ **اطلاعات پنل:** {panel_error_text(snapshot.panel_error)}")
        if snapshot.expire_at is not None:
            lines.append(f"📅 **آخرین انقضای ثبت‌شده:** {timestamp_to_persian_expiry(snapshot.expire_at)}")
        lines.extend(["", "ℹ️ با وجود در دسترس نبودن پنل، می‌توانید پیام پشتیبانی بفرستید."])

    warnings = service_warnings(snapshot)
    if warnings:
        lines.extend(["", *warnings])
    return "\n".join(lines)


def _live_lines(snapshot: ServiceSnapshot) -> list[str]:
    lines = []
    if snapshot.unlimited:
        lines.append("📦 **حجم:** ♾️ نامحدود")
    elif snapshot.data_limit_bytes:
        lines.append(f"📥 **حجم مصرفی:** {format_size(snapshot.used_bytes, decimal_places=2)}")
        lines.append(
            f"📦 **حجم باقی‌مانده:** {format_size(snapshot.remaining_bytes, decimal_places=2)}"
            f" از {format_size(snapshot.data_limit_bytes, decimal_places=2)}"
        )
    if snapshot.expire_at is not None:
        lines.append(f"📅 **انقضا:** {timestamp_to_persian_expiry(snapshot.expire_at)}")
    if snapshot.online_at is not None:
        lines.append(f"🔋 **آخرین اتصال:** {relative_time(snapshot.online_at)}")
    return lines


def _state_lines(snapshot: ServiceSnapshot) -> list[str]:
    if snapshot.state == STATE_ACTIVE:
        return [
            "",
            "✅ سرویس شما فعال است.",
            "🛠 در صورت وجود مشکل، با دکمهٔ «هنوز نیاز به پشتیبانی دارم» پیام پشتیبانی بفرستید.",
        ]
    if snapshot.state == STATE_EXPIRED:
        return ["", "⛔️ زمان این سرویس به پایان رسیده است.", _renew_hint(snapshot)]
    if snapshot.state == STATE_LIMITED:
        return ["", "⛔️ حجم این سرویس تمام شده است.", _volume_or_renew_hint(snapshot)]
    if snapshot.state == STATE_EXPIRED_LIMITED:
        return ["", "⛔️ هم زمان و هم حجم این سرویس تمام شده است.", _renew_hint(snapshot)]
    if snapshot.state == STATE_DISABLED:
        return [
            "",
            "⛔️ این سرویس توسط پنل غیرفعال شده است.",
            "ℹ️ دلیل غیرفعال شدن سرویس در اطلاعات پنل موجود نیست؛ برای بررسی بیشتر پیام پشتیبانی بفرستید.",
        ]
    if snapshot.state == STATE_ON_HOLD:
        return ["", "🔋 سرویس در انتظار اولین اتصال است؛ زمان آن بعد از اولین اتصال شروع می‌شود."]
    return [
        "",
        "ℹ️ وضعیت این سرویس قابل تشخیص نیست؛ می‌توانید با دکمهٔ زیر پیام پشتیبانی بفرستید.",
    ]


def _renew_hint(snapshot: ServiceSnapshot) -> str:
    if snapshot.can_renew:
        return "💡 با دکمهٔ «تمدید سرویس» می‌توانید اشتراک را ادامه دهید."
    return "💡 برای ادامه، پیام پشتیبانی بفرستید."


def _volume_or_renew_hint(snapshot: ServiceSnapshot) -> str:
    options = []
    if snapshot.can_buy_volume:
        options.append("«خرید حجم»")
    if snapshot.can_renew:
        options.append("«تمدید سرویس»")
    if not options:
        return "💡 برای ادامه، پیام پشتیبانی بفرستید."
    return f"💡 می‌توانید {' یا '.join(options)} انجام دهید."


def _status_buttons(snapshot: ServiceSnapshot, *, back_data: str) -> list[list]:
    rows: list[list] = []
    actions = []
    if snapshot.state in (STATE_EXPIRED, STATE_LIMITED, STATE_EXPIRED_LIMITED):
        if snapshot.can_renew:
            actions.append(_button("🔄 تمدید سرویس", f"TamdidVPN_{snapshot.code}", "primary"))
        if snapshot.state == STATE_LIMITED and snapshot.can_buy_volume:
            actions.append(_button("➕ خرید حجم", f"KharidSize:{snapshot.code}", "primary"))
    if actions:
        rows.append(actions)

    rows.append([_button("📨 هنوز نیاز به پشتیبانی دارم", f"{CB_CONTINUE}{snapshot.code}", "primary")])
    rows.append(
        [
            _button("☎️ موضوع عمومی / نمی‌دانم", CB_GENERAL),
            _button("🔙 بازگشت", back_data),
        ]
    )
    return rows


def _status_back_data(service_code: Any, services_total: int, origin: str | None) -> str:
    """Where "back" goes: the service page that opened the report, else the picker/home."""
    if origin == ORIGIN_SERVICE:
        return f"service_info:{service_code}"
    return f"{CB_PICK}1" if services_total > 1 else "home.back"


def _picker_label(card: ServiceSnapshot) -> str:
    return (
        f"{card_state_text(card)} | {_shorten(card.config_name, 24)} | {_shorten(card.panel_name, 14)} | کد {card.code}"
    )


# --------------------------------------------------------------------------- #
#  Callbacks                                                                   #
# --------------------------------------------------------------------------- #


async def support_callback_filter(event: events.CallbackQuery.Event) -> bool:
    data = (event.data or b"").decode("utf-8", "ignore")
    return data.startswith(CB_PREFIXES) or data in (CB_ALL, CB_GENERAL, CB_BACK)


@bot_is_offline
async def support_callback(event: events.CallbackQuery.Event):
    data = (event.data or b"").decode("utf-8", "ignore")
    user_id = event.sender_id

    if data.startswith(CB_PICK):
        await event.answer()
        await _render_picker(event, _int_or(data[len(CB_PICK) :], 1))
        return

    if data.startswith((CB_SERVICE, CB_REPORT)):
        prefix = CB_SERVICE if data.startswith(CB_SERVICE) else CB_REPORT
        service = await _owned_service(user_id, data[len(prefix) :])
        if service is None:
            await event.answer("❌ این سرویس برای شما نیست!", alert=True)
            return
        origin = ORIGIN_SERVICE if data.startswith(CB_REPORT) else ORIGIN_PICKER
        await event.answer()
        await _render_service_status(event, service, services_total=await _count_services(user_id), origin=origin)
        return

    if data == CB_ALL:
        await event.answer()
        await _render_all(event)
        return

    if data == CB_GENERAL:
        await event.answer()
        await _show_message_prompt(event, TARGET_GENERAL)
        return

    if data.startswith(CB_CONTINUE):
        await event.answer()
        await _show_message_prompt(event, data[len(CB_CONTINUE) :])
        return

    if data == CB_BACK:
        await event.answer()
        await _go_back(event)


# --------------------------------------------------------------------------- #
#  Helpers                                                                     #
# --------------------------------------------------------------------------- #


def _button(text: str, data: str, style: str | None = None):
    return styled_callback_button(text, data, build_telegram_button_style(style, None))


async def _render(event, text: str, buttons) -> None:
    """Edit the tapped message in place, or send a new one for typed commands."""
    if hasattr(event, "answer"):
        try:
            await event.edit(text, buttons=buttons, link_preview=False)
            return
        except MessageNotModifiedError:
            return
        except Exception as exc:
            logger.warning("support: edit failed, sending a new message: %s", exc)
    await event.respond(text, buttons=buttons, link_preview=False)


async def _support_text() -> str:
    return await get_bot_text(
        key="support_message",
        default=DEFAULT_BOT_TEXTS["support_message"],
        lang="fa",
    )


async def _user_services(user_id: int) -> list[Any]:
    return list(await ServiceCRUD().get_services_reverse(user_id=user_id))


async def _count_services(user_id: int) -> int:
    _, total = await get_user_services_paginated(user_id=user_id, page=1, limit=1)
    return int(total or 0)


async def _owned_service(user_id: int, code: Any) -> Any | None:
    """Only the sender's own services can be opened from a support screen."""
    ok, service = await ServiceCRUD().get_service(code=code)
    if not ok or not service:
        return None
    return service if service_belongs_to(service, user_id) else None


async def _normalized_target(user_id: int, raw: Any) -> tuple[str, Any | None]:
    """Coerce a stored/callback target into all | general | the user's own service code."""
    if raw == TARGET_ALL:
        return TARGET_ALL, None
    if raw == TARGET_GENERAL or raw is None:
        return TARGET_GENERAL, None
    service = await _owned_service(user_id, raw)
    if service is None:
        return TARGET_GENERAL, None
    return str(service.code), service


def _target_context_text(target: str, service: Any | None) -> str:
    if target == TARGET_ALL:
        return "همهٔ سرویس‌ها"
    if service is not None:
        return f"`{service.username}` (کد {service.code})"
    return "موضوع عمومی"


async def _safe_sender(event) -> Any | None:
    try:
        return await event.get_sender()
    except Exception as exc:
        logger.warning("support: could not read the sender of %s: %s", event.sender_id, exc)
        return None


def _display_name(sender: Any | None) -> str:
    if sender is None:
        return "کاربر"
    first_name = getattr(sender, "first_name", None) or ""
    last_name = getattr(sender, "last_name", None) or ""
    name = f"{first_name} {last_name}".strip()
    return name or getattr(sender, "username", None) or "کاربر"


def _shorten(value: str, limit: int) -> str:
    value = (value or "").strip()
    return value if len(value) <= limit else f"{value[: limit - 1]}…"


def _int_or(value: Any, default: int) -> int:
    try:
        return int(str(value).strip())
    except TypeError, ValueError:
        return default


def setup(kenzo: PluginContext) -> None:
    kenzo.add_event_handler(
        support_menu,
        events.NewMessage(incoming=True, func=support_menu_filter),
    )
    kenzo.add_event_handler(
        support_message,
        events.NewMessage(incoming=True, func=is_support_message),
    )
    kenzo.add_event_handler(
        support_screen_text,
        events.NewMessage(incoming=True, func=is_pending_support_text),
    )
    kenzo.add_event_handler(
        support_callback,
        events.CallbackQuery(func=support_callback_filter),
    )
