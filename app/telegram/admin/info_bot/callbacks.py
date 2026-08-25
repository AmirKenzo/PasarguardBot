"""Callback handlers for admin stats/info bot."""

from telethon import events
from telethon.errors.rpcerrorlist import MessageNotModifiedError

from app import CustomMarkdown
from app.logger import get_logger
from app.services.telegram.rich_message import edit_native_rich_message
from app.telegram.admin.info_bot import keyboards, service, states
from app.telegram.admin.top_customers import build_top_customers_message, top_customers_rich_blocks
from config import ADMIN_ID

logger = get_logger(__name__)


def stats_callback_filter(event: events.CallbackQuery.Event) -> bool:
    return event.sender_id in ADMIN_ID


async def stats_panel_callback(event: events.CallbackQuery.Event):
    data = (event.data or b"").decode().strip()
    action = data.removeprefix(states.STATS_PREFIX)
    try:
        await event.answer()

        if action in ("main", "refresh"):
            payload = await service.main_payload(force=action == "refresh")
            try:
                blocks = service.main_rich_blocks(payload)
                await edit_native_rich_message(event, blocks)
            except Exception as rich_exc:
                logger.warning("stats:main rich edit failed, falling back: %s", rich_exc)
                msg, entities = CustomMarkdown.parse(service.main_text(payload))
                await event.edit(msg, formatting_entities=entities, buttons=keyboards.main_menu_buttons())
            return

        if action == "revenue" or action.startswith("revenue:"):
            parts = action.split(":")
            period = parts[1] if len(parts) > 1 else "1d"
            if period not in states.REVENUE_PERIODS:
                period = "1d"
            force = len(parts) > 2 and parts[2] == "refresh"
            payload = await service._revenue_payload(period, force=force)
            try:
                blocks = service.revenue_rich_blocks(payload)
                await edit_native_rich_message(event, blocks)
            except Exception as rich_exc:
                logger.warning("stats:revenue rich edit failed, falling back: %s", rich_exc)
                msg, entities = CustomMarkdown.parse(service._revenue_text(payload))
                await event.edit(msg, formatting_entities=entities, buttons=keyboards.period_buttons("revenue", period))
            return

        if action.startswith("top:"):
            view = action.split(":", 1)[1]
            if view not in ("today", "spend", "recharge", "config"):
                view = "today"
            try:
                blocks = await top_customers_rich_blocks(view)
                await edit_native_rich_message(event, blocks)
            except Exception as rich_exc:
                logger.warning("stats:top rich edit failed, falling back: %s", rich_exc)
                msg, entities = await build_top_customers_message(view)
                await event.edit(msg, formatting_entities=entities, buttons=keyboards.top_buttons(view))
            return

        if action == "services" or action.startswith("services:"):
            parts = action.split(":")
            period = parts[1] if len(parts) > 1 else "1d"
            if period not in states.REVENUE_PERIODS:
                period = "1d"
            force = len(parts) > 2 and parts[2] == "refresh"
            payload = await service._services_payload(period, force=force)
            try:
                blocks = service.services_rich_blocks(payload)
                await edit_native_rich_message(event, blocks)
            except Exception as rich_exc:
                logger.warning("stats:services rich edit failed, falling back: %s", rich_exc)
                msg, entities = CustomMarkdown.parse(service._services_text(payload))
                await event.edit(
                    msg, formatting_entities=entities, buttons=keyboards.period_buttons("services", period)
                )
            return

        if action in ("system", "system:refresh"):
            ping_sec = await service._measure_ping()
            payload = await service._system_payload(force=action == "system:refresh")
            try:
                blocks = service.system_rich_blocks(payload, ping_sec)
                await edit_native_rich_message(event, blocks)
            except Exception as rich_exc:
                logger.warning("stats:system rich edit failed, falling back: %s", rich_exc)
                markdown = service._system_text(payload, ping_sec)
                msg, entities = CustomMarkdown.parse(markdown)
                await event.edit(msg, formatting_entities=entities, buttons=keyboards.system_buttons())
            return

    except MessageNotModifiedError:
        pass
    except Exception as exc:
        logger.error("Stats panel error [%s]: %s", action, exc)
        await event.answer("❌ خطا در بارگذاری آمار", alert=True)


def register(client):
    client.add_event_handler(
        stats_panel_callback,
        events.CallbackQuery(pattern=rb"^stats:", func=stats_callback_filter),
    )
