"""Admin support tickets, service cards, navigation and short-lived callback context."""

from __future__ import annotations

import html
import json
import math
import secrets
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from typing import Any

import jdatetime
from telethon import Button
from telethon.tl import types
from telethon.tl.custom import Message

from app import Kenzo
from app.db.crud.panels import PanelsManager
from app.db.crud.services import ServiceCRUD
from app.logger import get_logger
from app.services.support import (
    STATE_ACTIVE,
    STATE_DISABLED,
    STATE_EXPIRED,
    STATE_EXPIRED_LIMITED,
    STATE_LIMITED,
    STATE_ON_HOLD,
    STATE_UNKNOWN,
    ServiceSnapshot,
    build_service_card,
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
from app.services.telegram.rich_message import rt as _rt
from app.telegram.keyboards.common import build_telegram_button_style, styled_callback_button
from app.telegram.state.store import get_app_cache, set_app_cache
from app.utils.formatting.dates import IRAN_TZ, Time_Date, relative_time, timestamp_to_persian_expiry
from app.utils.formatting.traffic import format_size
from config import ADMIN_ID

logger = get_logger(__name__)

TARGET_ALL = "all"
TARGET_GENERAL = "general"

FILTER_ALL = "all"
FILTER_ACTIVE = "active"

TICKET_CACHE_PREFIX = "support:ticket"
TICKET_TTL_SECONDS = 7 * 24 * 3600
LIST_CACHE_PREFIX = "support:adminlist"
LIST_TTL_SECONDS = 24 * 3600

TICKET_HEADING = "🏷 <b>تیکت پشتیبانی</b>"
RAIL = "│"
SERVICES_PER_PAGE = 5
# Above this many services the list trusts the stored status instead of
# reading every service from the panel just to draw one page of buttons.
LIVE_STATE_LIMIT = 20


@dataclass(frozen=True, slots=True)
class SupportTicket:
    """What stays attached to one support message."""

    user_id: int
    target: str
    text: str
    sender_name: str = "کاربر"
    sender_username: str | None = None
    created_at: int = 0
    token: str = ""


@dataclass(frozen=True, slots=True)
class ServiceCard:
    """The service part of a ticket: a title, label/value rows and an optional note."""

    title: str
    rows: tuple[tuple[str, Any], ...]
    note: str = ""


@dataclass(frozen=True, slots=True)
class ServicesListContext:
    """State behind the admin's service list, addressed by a short token."""

    user_id: int
    target: str = TARGET_GENERAL
    filter: str = FILTER_ALL
    page: int = 1
    sender_name: str | None = None


def mint_token() -> str:
    """Short token that ties a button back to its cached payload."""
    return secrets.token_hex(5)


def mint_list_context() -> str:
    return secrets.token_hex(4)


def target_service_code(target: str) -> int | None:
    value = str(target)
    return int(value) if value.isdigit() else None


# --------------------------------------------------------------------------- #
#  Cache                                                                       #
# --------------------------------------------------------------------------- #


def _cache_key(token: str) -> str:
    return f"{TICKET_CACHE_PREFIX}:{token}"


def _list_cache_key(token: str) -> str:
    return f"{LIST_CACHE_PREFIX}:{token}"


async def remember_ticket(ticket: SupportTicket) -> None:
    if not ticket.token:
        return
    try:
        payload = json.dumps(asdict(ticket), ensure_ascii=False)
    except TypeError, ValueError:
        return
    await set_app_cache(_cache_key(ticket.token), payload, ttl_seconds=TICKET_TTL_SECONDS)


async def recall_ticket(token: str) -> SupportTicket | None:
    if not token:
        return None
    raw = await get_app_cache(_cache_key(token))
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return SupportTicket(
            user_id=int(data["user_id"]),
            target=str(data["target"]),
            text=str(data.get("text") or ""),
            sender_name=str(data.get("sender_name") or "کاربر"),
            sender_username=data.get("sender_username") or None,
            created_at=int(data.get("created_at") or 0),
            token=str(data.get("token") or token),
        )
    except KeyError, TypeError, ValueError:
        return None


async def remember_list_context(token: str, context: ServicesListContext) -> None:
    if not token:
        return
    try:
        payload = json.dumps(asdict(context), ensure_ascii=False)
    except TypeError, ValueError:
        return
    await set_app_cache(_list_cache_key(token), payload, ttl_seconds=LIST_TTL_SECONDS)


async def recall_list_context(token: str) -> ServicesListContext | None:
    if not token:
        return None
    raw = await get_app_cache(_list_cache_key(token))
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return ServicesListContext(
            user_id=int(data["user_id"]),
            target=str(data.get("target") or TARGET_GENERAL),
            filter=str(data.get("filter") or FILTER_ALL),
            page=int(data.get("page") or 1),
            sender_name=data.get("sender_name") or None,
        )
    except KeyError, TypeError, ValueError:
        return None


# --------------------------------------------------------------------------- #
#  Service facts                                                               #
# --------------------------------------------------------------------------- #


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def _volume_text(snapshot: ServiceSnapshot) -> str:
    if snapshot.unlimited:
        return "♾️ نامحدود"
    if snapshot.remaining_bytes is None:
        return "نامشخص"
    if snapshot.data_limit_bytes:
        return f"{format_size(snapshot.remaining_bytes)} از {format_size(snapshot.data_limit_bytes)}"
    return format_size(snapshot.remaining_bytes)


def _warning_text(snapshot: ServiceSnapshot) -> str:
    warnings = [line.removeprefix("🟡 ").strip() for line in service_warnings(snapshot)]
    return f"🟡 {' · '.join(warnings)}" if warnings else ""


async def load_service_card(user_id: int, target: str) -> ServiceCard:
    code = target_service_code(target)
    if code is None:
        return ServiceCard(title="سرویس مرتبط", rows=(("وضعیت", "❌ نامشخص"),))

    ok, service = await ServiceCRUD().get_service(code=code)
    if not ok or not service:
        return ServiceCard(title="سرویس مرتبط", rows=(("وضعیت", f"❌ سرویس با کد {code} پیدا نشد"),))

    # Only the ticket owner's own service may appear, even if a callback is forged.
    if not service_belongs_to(service, user_id):
        logger.warning("support ticket: service %s does not belong to user %s", code, user_id)
        return ServiceCard(title="سرویس مرتبط", rows=(("وضعیت", "❌ این سرویس به این کاربر تعلق ندارد"),))

    try:
        snapshot = await load_service_snapshot(service)
    except Exception as exc:  # a ticket must still go out
        logger.warning("support ticket: snapshot failed for service %s: %s", code, exc)
        return ServiceCard(
            title="سرویس مرتبط",
            rows=(
                ("نام کانفیگ", service.username),
                ("کد سرویس", service.code),
                ("اطلاعات سرویس", "⚪️ در دسترس نیست"),
            ),
        )

    rows: list[tuple[str, Any]] = [
        ("نام کانفیگ", snapshot.config_name),
        ("کد سرویس", snapshot.code),
        ("پنل", snapshot.panel_name),
    ]
    if snapshot.is_test:
        rows.append(("نوع سرویس", "🧪 تست"))
    if snapshot.panel_available:
        rows.append(("وضعیت", state_label(snapshot.state)))
        if snapshot.unlimited or snapshot.data_limit_bytes:
            rows.append(("حجم", _volume_text(snapshot)))
        if snapshot.used_bytes is not None:
            rows.append(("مصرف", format_size(snapshot.used_bytes)))
        expiry = snapshot.expire_at
        if expiry is not None:
            rows.append(("انقضا", timestamp_to_persian_expiry(expiry)))
        if snapshot.online_at is not None:
            rows.append(("آخرین اتصال", relative_time(snapshot.online_at)))
    else:
        rows.append(("وضعیت", "⚪️ نامشخص"))
        rows.append(("اطلاعات پنل", panel_error_text(snapshot.panel_error)))
        expiry = snapshot.expire_at
        if expiry is not None:
            rows.append(("انقضا", f"{timestamp_to_persian_expiry(expiry)} (ثبت‌شده)"))
    warning = _warning_text(snapshot)
    if warning:
        rows.append(("هشدار", warning))
    return ServiceCard(title="سرویس مرتبط", rows=tuple(rows))


async def _all_services_card(user_id: int) -> ServiceCard:
    try:
        overview = await load_services_overview(user_id)
    except Exception as exc:
        logger.warning("support ticket: overview failed for %s: %s", user_id, exc)
        return ServiceCard(title="سرویس مرتبط", rows=(("وضعیت", "❌ اطلاعات در دسترس نیست"),))

    if not overview.total:
        return ServiceCard(title="سرویس مرتبط", rows=(("وضعیت", "کاربر سرویسی ندارد"),))

    rows: list[tuple[str, Any]] = [
        ("تعداد کل", overview.total),
        ("فعال", overview.count(STATE_ACTIVE)),
        ("منقضی", overview.count(STATE_EXPIRED)),
        ("نامشخص", overview.count(STATE_UNKNOWN)),
    ]
    if overview.expiring_soon:
        rows.append(("🟡 نزدیک انقضا", overview.expiring_soon))
    note = "جزئیات هر سرویس با دکمهٔ «جزئیات همهٔ سرویس‌ها» باز می‌شود."
    return ServiceCard(title="سرویس مرتبط — همهٔ سرویس‌ها", rows=tuple(rows), note=note)


async def _service_card(ticket: SupportTicket) -> ServiceCard | None:
    if ticket.target == TARGET_GENERAL:
        return None
    if ticket.target == TARGET_ALL:
        return await _all_services_card(ticket.user_id)
    return await load_service_card(ticket.user_id, ticket.target)


# --------------------------------------------------------------------------- #
#  Ticket rendering                                                            #
# --------------------------------------------------------------------------- #


def _card_lines(card: ServiceCard) -> list[str]:
    """One fact per line, each starting with a rail so the lines never blur together."""
    lines = [f"<b>{_esc(card.title)}</b>"]
    lines.extend(f"{RAIL} <b>{_esc(label)}</b> · {_esc(value)}" for label, value in card.rows)
    if card.note:
        lines.append(f"<i>{_esc(card.note)}</i>")
    return lines


async def build_ticket_view(ticket: SupportTicket) -> tuple[str, list[list]]:
    """HTML body and buttons for one ticket. Never raises for a panel problem."""
    lines = [TICKET_HEADING, ""]
    sender = (
        f'<a href="tg://user?id={int(ticket.user_id)}"><b>{_esc(ticket.sender_name)}</b></a>'
        f" · <code>{int(ticket.user_id)}</code>"
    )
    if ticket.sender_username:
        sender += f" · @{_esc(ticket.sender_username)}"
    lines.append(sender)
    if ticket.created_at:
        stamp = Time_Date(ticket.created_at).get("jf")
        if stamp:
            lines.append(f"<code>{_esc(stamp)}</code>")

    try:
        card = await _service_card(ticket)
    except Exception as exc:  # never lose the customer text because of a section
        logger.warning("support ticket: service section failed for %s: %s", ticket.user_id, exc)
        card = ServiceCard(title="سرویس مرتبط", rows=(("وضعیت", "⚪️ اطلاعات در دسترس نیست"),))
    if card is not None:
        lines.extend(["", *_card_lines(card)])

    lines.extend(["", "<b>متن مشتری</b>", f"<blockquote expandable>{_esc(ticket.text)}</blockquote>"])
    return "\n".join(lines), ticket_buttons(ticket)


def ticket_buttons(ticket: SupportTicket) -> list[list]:
    """Reply, refresh and the user's services — always below the card."""
    reply_row = [Button.inline("📨 پاسخ به کاربر", f"sendm_{ticket.user_id}")]
    if ticket.target != TARGET_GENERAL and ticket.token:
        reply_row.append(
            Button.inline("🔄 به‌روزرسانی اطلاعات", f"supref:{ticket.user_id}:{ticket.target}:{ticket.token}")
        )

    other_label = "📋 جزئیات همهٔ سرویس‌ها" if ticket.target == TARGET_ALL else "📋 سایر سرویس‌های کاربر"
    token_suffix = f":{ticket.token}" if ticket.token else ""
    return [
        reply_row,
        [Button.inline(other_label, f"supoth:{ticket.user_id}:0:{ticket.target}{token_suffix}")],
        [Button.inline("⛔️ مسدود کردن", f"bansup_{ticket.user_id}")],
    ]


async def _send_html(chat_id: int, text: str, buttons) -> None:
    await Kenzo.send_message(chat_id, text, buttons=buttons, parse_mode="html", link_preview=False)


async def send_ticket_to_admins(ticket: SupportTicket) -> int:
    """Send one ticket to every admin; returns how many chats accepted it."""
    text, buttons = await build_ticket_view(ticket)
    delivered = 0
    for admin_id in ADMIN_ID:
        try:
            await _send_html(admin_id, text, buttons)
        except Exception as exc:
            logger.warning("support ticket: delivery to admin %s failed: %s", admin_id, exc)
            continue
        delivered += 1
    if delivered:
        await remember_ticket(ticket)
    return delivered


# --------------------------------------------------------------------------- #
#  Admin: the user's services (list → detail)                                  #
# --------------------------------------------------------------------------- #


def _state_counts(cards: list[ServiceSnapshot]) -> str:
    """Compact count line for the list header; active/expired are always shown."""
    buckets = (
        ("فعال", (STATE_ACTIVE, STATE_ON_HOLD), True),
        ("منقضی", (STATE_EXPIRED,), True),
        ("حجم تمام", (STATE_LIMITED,), False),
        ("زمان+حجم", (STATE_EXPIRED_LIMITED,), False),
        ("غیرفعال", (STATE_DISABLED,), False),
        ("نامشخص", (STATE_UNKNOWN,), False),
    )
    parts = []
    for label, states, always in buckets:
        count = sum(1 for card in cards if card.state in states)
        if count or always:
            parts.append(f"{label} {count}")
    return " · ".join(parts)


def _shorten(value: str, limit: int) -> str:
    value = (value or "").strip()
    return value if len(value) <= limit else f"{value[: limit - 1]}…"


def _filter_button(label: str, context_token: str, filter_value: str, selected: bool):
    style = "primary" if selected else None
    return styled_callback_button(
        label,
        f"supl:{context_token}:{filter_value}:1",
        build_telegram_button_style(style, None),
    )


def _page_button(label: str, context_token: str, filter_value: str, page: int):
    return styled_callback_button(label, f"supl:{context_token}:{filter_value}:{page}")


def _passes_filter(card: ServiceSnapshot, filter_value: str, *, live: bool) -> bool:
    if filter_value != FILTER_ACTIVE:
        return True
    if live:
        return card.state in (STATE_ACTIVE, STATE_ON_HOLD)
    return card.state != STATE_EXPIRED


@dataclass(frozen=True, slots=True)
class ServicesPage:
    """Everything both renderers (rich and HTML) need for one page of the list."""

    context: ServicesListContext
    cards: tuple[ServiceSnapshot, ...]
    total: int
    pages: int
    page: int
    counts: str
    live: bool


async def _load_services_page(
    context: ServicesListContext,
    *,
    now: datetime | None = None,
) -> ServicesPage:
    services = await ServiceCRUD().get_services_reverse(user_id=context.user_id)
    panels_by_code = {panel.code: panel for panel in await PanelsManager().get_all_panels()}
    db_cards = {
        service.code: build_service_card(service, panels_by_code.get(service.in_panel), now=now) for service in services
    }

    ticket_code = target_service_code(context.target)
    others = [service for service in services if ticket_code is None or int(service.code) != ticket_code]

    # Reading the panel for every service keeps the filter and the button colours
    # honest; past a sane size the list falls back to the stored status.
    live = len(others) <= LIVE_STATE_LIMIT
    if live:
        try:
            cards = await load_service_states(others, panels_by_code=panels_by_code, now=now)
        except Exception as exc:
            logger.warning("support list: live states failed for %s: %s", context.user_id, exc)
            live = False
            cards = [db_cards[int(service.code)] for service in others]
    else:
        cards = [db_cards[int(service.code)] for service in others]

    pool = [
        (service, card)
        for service, card in zip(others, cards, strict=True)
        if _passes_filter(card, context.filter, live=live)
    ]
    pages = max(1, math.ceil(len(pool) / SERVICES_PER_PAGE))
    page = min(max(1, context.page), pages)
    chunk = [card for _service, card in pool[(page - 1) * SERVICES_PER_PAGE : page * SERVICES_PER_PAGE]]

    return ServicesPage(
        context=context,
        cards=tuple(chunk),
        total=len(others),
        pages=pages,
        page=page,
        counts=_state_counts(cards),
        live=live,
    )


def _list_filter_label(context: ServicesListContext) -> str:
    return "همه" if context.filter == FILTER_ALL else "فقط فعال"


def _list_hint(page: ServicesPage) -> str:
    if not page.cards:
        return "سرویسی با این فیلتر پیدا نشد."
    if not page.live:
        return "وضعیت‌ها از اطلاعات ثبت‌شده است؛ برای رنگ و فیلتر دقیق، تعداد سرویس‌ها باید کمتر باشد."
    return "برای دیدن مشخصات هر سرویس، دکمهٔ آن را بزن."


def _service_row_label(card: ServiceSnapshot) -> str:
    return f"{card_state_text(card)} · {_shorten(card.config_name, 24)} · کد {card.code}"


# --------------------------------------------------------------------------- #
#  Admin list/detail: rich renderer (buttons live inside the message)           #
# --------------------------------------------------------------------------- #


def _plain(value: Any) -> types.TextPlain:
    return types.TextPlain(text=str(value if value is not None else ""))


RICH_STYLES: dict[str | None, types.RichButtonStyle | None] = {
    "success": types.RichButtonStyle(bg_success=True),
    "danger": types.RichButtonStyle(bg_danger=True),
    "primary": types.RichButtonStyle(bg_primary=True),
    None: None,
}


def _rich_button(label: str, data: str, style: str | None = None) -> types.PageButton:
    return types.PageButton(
        text=_plain(label),
        type=types.InlineButtonTypeCallback(data=data.encode("utf-8")),
        style=RICH_STYLES.get(style),
    )


def _rich_row(*buttons: types.PageButton) -> types.PageBlockButtonRow:
    return types.PageBlockButtonRow(buttons=list(buttons))


def _rich_table(title: str, rows: tuple[tuple[str, Any], ...]) -> types.PageBlockTable:
    return types.PageBlockTable(
        title=_rt(title),
        bordered=True,
        compact=True,
        rows=[
            types.PageTableRow(
                cells=[
                    types.PageTableCell(text=types.TextBold(_rt(label))),
                    types.PageTableCell(text=_plain(value)),
                ]
            )
            for label, value in rows
        ],
    )


def build_admin_service_detail_rich(context_token: str, code: int, card: ServiceCard) -> list:
    """Rich detail card for one service with the back button inside the message."""
    return [
        types.PageBlockParagraph(types.TextBold(_plain("🔎 مشخصات سرویس"))),
        _rich_table(f"سرویس {code}", card.rows),
        types.PageBlockDivider(),
        _rich_row(_rich_button("🔙 بازگشت به لیست", f"supb:{context_token}")),
    ]


def ticket_from_message(message: Message | None, user_id: int, target: str) -> SupportTicket | None:
    """Recover a ticket from its formatting entities without interpreting customer data."""
    if message is None:
        return None
    quotes = message.get_entities_text(types.MessageEntityBlockquote)
    names = message.get_entities_text(types.MessageEntityBold)
    if len(quotes) != 1 or not quotes[0][1] or len(names) < 2:
        return None

    sender_name = names[1][1]
    sender_tail = (message.message or "").partition(f"{sender_name} · {int(user_id)}")[2].split("\n", 1)[0]
    sender_username = sender_tail.removeprefix(" · @") if sender_tail.startswith(" · @") else None
    codes = message.get_entities_text(types.MessageEntityCode)
    created_at = 0
    if len(codes) > 1:
        try:
            local_time = jdatetime.datetime.strptime(codes[1][1], "%Y/%m/%d %H:%M:%S").togregorian()
            created_at = int(IRAN_TZ.localize(local_time).timestamp())
        except ValueError:
            return None
    return SupportTicket(
        user_id=int(user_id),
        target=str(target),
        text=quotes[0][1],
        sender_name=sender_name,
        sender_username=sender_username,
        created_at=created_at,
        token=mint_token(),
    )


# --------------------------------------------------------------------------- #
#  Admin list/detail: HTML fallback (same content, inline keyboard below)       #
# --------------------------------------------------------------------------- #


async def build_admin_services_list(
    context_token: str,
    context: ServicesListContext,
    *,
    now: datetime | None = None,
) -> tuple[str, list[list]]:
    """HTML fallback: one inline button per service, with the all/active filter."""
    page = await _load_services_page(context, now=now)
    header = (
        f"👤 <b>{_esc(context.sender_name)}</b> · <code>{int(context.user_id)}</code>"
        if context.sender_name
        else f"👤 <code>{int(context.user_id)}</code>"
    )
    lines = [
        header,
        f"تعداد: <b>{page.total}</b> · {_esc(page.counts)}",
        f"فیلتر: <b>{_list_filter_label(context)}</b> · صفحه {page.page} از {page.pages}",
        "",
        f"<i>{_esc(_list_hint(page))}</i>",
    ]

    rows: list[list] = []
    for card in page.cards:
        rows.append(
            [
                styled_callback_button(
                    _service_row_label(card),
                    f"supd:{context_token}:{card.code}",
                    build_telegram_button_style(state_style(card.state), None),
                )
            ]
        )

    rows.append(
        [
            _filter_button("همه", context_token, FILTER_ALL, context.filter == FILTER_ALL),
            _filter_button("فقط فعال", context_token, FILTER_ACTIVE, context.filter == FILTER_ACTIVE),
        ]
    )

    navigation = []
    if page.page > 1:
        navigation.append(_page_button("◀️ صفحه قبل", context_token, context.filter, page.page - 1))
    if page.page < page.pages:
        navigation.append(_page_button("صفحه بعد ▶️", context_token, context.filter, page.page + 1))
    if navigation:
        rows.append(navigation)

    return "\n".join(lines), rows


def build_admin_service_detail(context_token: str, code: int, card: ServiceCard) -> tuple[str, list[list]]:
    """HTML fallback for the detail card, with a back button below it."""
    lines = ["🔎 <b>مشخصات سرویس</b>", ""]
    lines.extend(_card_lines(replace(card, title=f"سرویس {code}")))
    buttons = [[styled_callback_button("🔙 بازگشت به لیست", f"supb:{context_token}")]]
    return "\n".join(lines), buttons
