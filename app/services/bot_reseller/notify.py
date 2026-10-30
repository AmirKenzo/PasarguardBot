"""Messages to bot resellers (bot texts, editable by the admin) and to the reseller log channel."""

from __future__ import annotations

from app import Kenzo
from app.db.crud.keyboards import KeyboardButtonCRUD
from app.logger import LogType, get_logger
from app.services.send_queue import enqueue
from app.telegram.keyboards.common import _get_keyboard_button_config, styled_webview_button
from app.telegram.keyboards.registry import KEYBOARD_BUTTON_DEFAULTS
from app.telegram.shared.utils.miniapp import miniapp_deeplink, miniapp_ready
from app.utils.text.bot_texts import get_bot_text
from app.utils.text.default_texts import DEFAULT_BOT_TEXTS

log = get_logger(__name__)

WEBAPP_PATH = "/bot-reseller"
OPEN_BUTTON_KEY = "in.brs.open_panel"


def _fill(text: str, values: dict[str, object]) -> str:
    for key, value in values.items():
        text = text.replace("{" + key + "}", str(value))
    return text


async def bot_text(key: str, **values: object) -> str:
    return _fill(await get_bot_text(key=key, default=DEFAULT_BOT_TEXTS.get(key, key), lang="fa"), values)


async def open_panel_button():
    """Inline web-app button that lands on the reseller panel, or None when the mini app is not set up."""
    if not miniapp_ready():
        return None
    label, style = await _get_keyboard_button_config(
        KeyboardButtonCRUD(), OPEN_BUTTON_KEY, KEYBOARD_BUTTON_DEFAULTS[OPEN_BUTTON_KEY], default_style="primary"
    )
    return styled_webview_button(label, miniapp_deeplink(WEBAPP_PATH), style)


async def notify_reseller(telegram_id: int, key: str, *, with_panel_button: bool = False, **values: object) -> None:
    try:
        text = await bot_text(key, **values)
        button = await open_panel_button() if with_panel_button else None
        buttons = [[button]] if button is not None else None
        await Kenzo.send_message(int(telegram_id), text, buttons=buttons, parse_mode="markdown")
    except Exception as exc:
        log.warning("bot reseller notify failed user=%s key=%s: %s", telegram_id, key, exc)


async def log_event(title: str, lines: list[str]) -> None:
    message = "\n".join([f"<b>{title}</b>", "", *[line for line in lines if line]]).strip()
    await enqueue(message=message, log_type=LogType.RESELLER, parse_mode="html")
