"""Bot reseller entry points in the bot: pick a service and send a request, or open the web app panel.

Users are never managed here; the bot only sells the right (after admin approval) and links
to the web app.
"""

from __future__ import annotations

import time

from telethon import events

from app.db.crud.bot_reseller import BotResellerCRUD
from app.db.models.bot_reseller import (
    GRANT_APPROVED,
    GRANT_PENDING,
    RESELLER_FROZEN,
    RESELLER_SUSPENDED,
)
from app.services.bot_reseller import core
from app.services.bot_reseller.notify import open_panel_button
from app.services.reseller.purchase import bot_reseller_sale_open
from app.telegram.keyboards import reseller as rs_buttons
from app.telegram.user.reseller.helpers import get_reseller_text, reseller_flow_edit
from app.utils.formatting.traffic import format_size
from app.utils.text.default_texts import DEFAULT_BOT_TEXTS

CB_SERVICES = "BotReseller_services"
CB_SERVICE = "BotReseller_service:"
CB_REQUEST = "BotReseller_request:"
CB_HOME = "BotReseller_home"


async def _text(key: str, user_id: int | None, **values: object) -> str:
    return await get_reseller_text(key, DEFAULT_BOT_TEXTS[key], user_id, **{k: str(v) for k, v in values.items()})


async def _refusal(exc: core.Refused, user_id: int) -> str:
    """The editable text for a refusal when it names one, otherwise its built-in message."""
    return await _text(exc.key, user_id) if exc.key in DEFAULT_BOT_TEXTS else str(exc)


async def entry_rows() -> list:
    """The bot reseller button for the buy-reseller picker, when its sale is open."""
    if not await bot_reseller_sale_open():
        return []
    return [[await rs_buttons.brs_entry_button(CB_SERVICES)]]


async def my_rows(user_id: int) -> list:
    """The glass button in "my resellers", for anyone with an approved service (sales open or not)."""
    if not await BotResellerCRUD().has_approved_grant(user_id):
        return []
    reseller = await BotResellerCRUD().get_reseller_by_user(user_id)
    suffix = ""
    if reseller is not None and reseller.status == RESELLER_FROZEN:
        suffix = " · ⛔️"
    elif reseller is not None and reseller.status == RESELLER_SUSPENDED:
        suffix = " · ⏸"
    return [[await rs_buttons.brs_my_entry_button(CB_HOME, suffix=suffix)]]


async def _grant_status(user_id: int) -> dict[int, str]:
    crud = BotResellerCRUD()
    reseller = await crud.get_reseller_by_user(user_id)
    if reseller is None:
        return {}
    return {g.service_id: g.status for g in await crud.list_grants(reseller_id=reseller.id)}


async def _show_services(event) -> None:
    user_id = event.sender_id
    services = await BotResellerCRUD().list_services(sale_only=True)
    if not services:
        await event.answer(await _text("bot_reseller_no_services", user_id), alert=True)
        return
    statuses = await _grant_status(user_id)
    rows = []
    for service in services:
        status = statuses.get(service.id)
        if status == GRANT_APPROVED:
            label = f"✅ {service.name}"
        elif status == GRANT_PENDING:
            label = f"⏳ {service.name}"
        else:
            label = f"📦 {service.name} · {service.price_per_gb:,} / GB"
        rows.append([rs_buttons.brs_plain_button(label, f"{CB_SERVICE}{service.id}")])
    rows.append([await rs_buttons.brs_back_button("ResellerBuy_back_panels")])
    await reseller_flow_edit(event, await _text("bot_reseller_intro", user_id), buttons=rows)


def _limit(value: float) -> str:
    """A service limit as a bare number; the unit is part of the editable text, ∞ means no limit."""
    return f"{value:g}" if value else "∞"


async def _show_service(event, service_id: int) -> None:
    user_id = event.sender_id
    service = await BotResellerCRUD().get_service(service_id)
    if service is None or not service.sale_enabled:
        await event.answer(await _text("bot_reseller_no_services", user_id), alert=True)
        return
    status = (await _grant_status(user_id)).get(service.id)
    text = await _text(
        "bot_reseller_service_detail",
        user_id,
        service=service.name,
        price=f"{service.price_per_gb:,}",
        max_users=_limit(service.max_users),
        max_gb=_limit(service.max_user_gb),
        max_days=_limit(service.max_user_days),
        description=service.description or "",
    )
    rows = []
    if status == GRANT_APPROVED:
        button = await open_panel_button()
        if button is not None:
            rows.append([button])
    elif status == GRANT_PENDING:
        await event.answer(core.ALREADY_PENDING)
    else:
        rows.append([await rs_buttons.brs_request_button(f"{CB_REQUEST}{service.id}")])
    rows.append([await rs_buttons.brs_back_button(CB_SERVICES)])
    await reseller_flow_edit(event, text, buttons=rows)


async def _request(event, service_id: int) -> None:
    user_id = event.sender_id
    try:
        grant = await core.request_service(user_id, service_id)
    except core.Refused as exc:
        await event.answer(await _refusal(exc, user_id), alert=True)
        return
    service = await BotResellerCRUD().get_service(grant.service_id)
    text = await _text("bot_reseller_request_sent", user_id, service=service.name if service else "-")
    await reseller_flow_edit(event, text, buttons=[[await rs_buttons.brs_back_button(CB_SERVICES)]])


async def _show_home(event) -> None:
    user_id = event.sender_id
    try:
        ctx = await core.load_context(user_id)
    except core.Refused as exc:
        await event.answer(await _refusal(exc, user_id), alert=True)
        return
    crud = BotResellerCRUD()
    balance = (await crud.balances([user_id])).get(user_id, 0)
    counts = await crud.count_users(ctx.reseller.id)
    used, spent = (await crud.usage_totals(since=int(time.time()) - 86400, reseller_id=ctx.reseller.id)).get(
        ctx.reseller.id, (0, 0.0)
    )
    services = " · ".join(f"{ctx.services[g.service_id].name} ({counts.get(g.service_id, 0)})" for g in ctx.approved())
    status = "✅"
    if ctx.reseller.status == RESELLER_FROZEN:
        status = "⛔️"
    elif ctx.reseller.status == RESELLER_SUSPENDED:
        status = "⏸"
    text = await _text(
        "bot_reseller_home",
        user_id,
        balance=f"{balance:,}",
        services=services or "-",
        users=sum(counts.values()),
        today=f"{format_size(used)} · {round(spent):,}",
        status=status,
    )
    rows = []
    button = await open_panel_button()
    if button is not None:
        rows.append([button])
    rows.append([await rs_buttons.brs_back_list_button()])
    await event.edit(text, buttons=rows)


async def bot_reseller_callback(event: events.CallbackQuery.Event) -> None:
    if not event.is_private:
        return
    data = event.data.decode("utf-8")

    if data == CB_HOME:
        await _show_home(event)
        return

    if not await bot_reseller_sale_open():
        await event.answer(await _text("bot_reseller_no_services", event.sender_id), alert=True)
        return
    if data == CB_SERVICES:
        await _show_services(event)
    elif data.startswith(CB_SERVICE):
        await _show_service(event, int(data.split(":", 1)[1]))
    elif data.startswith(CB_REQUEST):
        await _request(event, int(data.split(":", 1)[1]))


def register(client) -> None:
    client.add_event_handler(bot_reseller_callback, events.CallbackQuery(pattern=rb"^BotReseller_"))
