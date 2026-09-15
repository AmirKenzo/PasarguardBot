"""Shared helpers for user start module."""

from __future__ import annotations

from telethon import Button, functions, types
from telethon.tl.custom import Message

from app import Kenzo
from app.db.crud.settings import SettingsManager
from app.db.crud.user import UserCRUD, add_user, get_user_status
from app.db.models.settings import DEFAULT_CORE_SETTINGS
from app.db.redis import get_redis
from app.logger import get_logger
from app.services.billing.sticky_discount import (
    apply_sticky_discount,
    format_sticky_applied_message,
    get_sticky_discount,
    parse_discount_start_param,
)
from app.services.keyboard_glass import glass_mode_active
from app.telegram.keyboards.home import bhome_buttons, miniapp_only_active
from app.telegram.shared.guards.channel_gate import (
    CHANNEL_JOIN_MESSAGE,
    build_channel_join_buttons,
    extract_start_param,
    get_not_joined_channels,
    is_reserved_start_param,
)
from app.telegram.shared.start_params import find_app_key_by_start_param, is_welcome_start_param
from app.telegram.state.keys import get_redis_namespace
from app.utils.formatting.dates import Time_Date
from app.utils.text.bot_texts import get_bot_text

logger = get_logger(__name__)

BOT_LANGUAGE = "fa"
_START_REACTION_KEY = "feature:start_reaction"


DEFAULT_START_MESSAGE = (
    "**🎈تبریک! به قندشکن خوش آمدید!**\n"
    "**🛍 خرید سرویس پرسرعت و تحویل آنی**\n"
    "**📊 تعرفه نیم بها**\n"
    "**🔗 مناسب همه اپراتور ها**\n"
    "**⚡️ بدون قطعی و پرسرعت**\n"
    "**‼️ از این پایین یک گزینه رو انتخاب کن !**"
)


DEFAULT_MINIAPP_ONLY_MESSAGE = (
    "**🚀 برای استفاده از سرویس، وارد اپلیکیشن شوید.**\nخرید، تمدید و مدیریت سرویس‌ها همه از همان‌جا انجام می‌شود."
)


def _core_setting(setting, key: str):
    """Read one core setting, falling back to its packaged default."""
    default = DEFAULT_CORE_SETTINGS.get(key)
    return default if setting is None else getattr(setting, key, default)


async def get_user_lang(user_id: int) -> str:
    info = await UserCRUD().read_user(user_id)
    return info.language if info and info.language else BOT_LANGUAGE


async def fetch_welcome_text(lang: str = BOT_LANGUAGE) -> str:
    """The text that accompanies the home keyboard.

    In mini-app-only mode the bot's menu is gone, so the usual "pick an option
    below" wording would point at nothing; that mode gets its own text.
    """
    setting = await SettingsManager().get_settings()
    if miniapp_only_active(setting):
        return await get_bot_text(key="miniapp_only_message", default=DEFAULT_MINIAPP_ONLY_MESSAGE, lang=lang)
    return await get_bot_text(key="start_message", default=DEFAULT_START_MESSAGE, lang=lang)


def _start_reaction_redis_key() -> str:
    return f"{get_redis_namespace()}:{_START_REACTION_KEY}"


async def is_start_reaction_enabled() -> bool:
    redis = await get_redis()
    if redis is None:
        return True
    try:
        value = await redis.get(_start_reaction_redis_key())
    except Exception as exc:
        logger.warning("Redis get start_reaction: %s", exc)
        return True
    if value is None:
        return True
    return value not in {"0", "false", "False", "off", "OFF"}


async def toggle_start_reaction() -> bool:
    enabled = not await is_start_reaction_enabled()
    redis = await get_redis()
    if redis is None:
        return enabled
    try:
        await redis.set(_start_reaction_redis_key(), "1" if enabled else "0")
    except Exception as exc:
        logger.warning("Redis set start_reaction: %s", exc)
    return enabled


def resolve_app_download_param(param: str | None) -> str | None:
    """Return app key when param triggers a download; welcome/legacy params are ignored."""
    if is_welcome_start_param(param):
        return None
    return find_app_key_by_start_param(param)


async def _drop_reply_keyboard(user_id: int) -> None:
    """Take down a reply keyboard left over from before the menu moved in-chat.

    Telegram only replaces a reply keyboard when a message carries a new one,
    and the in-chat menu is inline, so without this the old keyboard would sit
    under the composer next to its own replacement.
    """
    try:
        placeholder = await Kenzo.send_message(entity=user_id, message="⏳", buttons=Button.clear())
        await placeholder.delete()
    except Exception as exc:
        logger.debug("Could not clear the reply keyboard for %s: %s", user_id, exc)


async def send_welcome_menu(event: Message, welcome_text: str, lang: str) -> None:
    reaction_on = await is_start_reaction_enabled()
    setting = await SettingsManager().get_settings()
    if glass_mode_active(setting):
        await _drop_reply_keyboard(event.sender_id)
    # Both are admin-editable: clearing the emoji or zeroing the effect turns
    # that half off without touching the other.
    emoji = str(_core_setting(setting, "start_reaction_emoji") or "").strip()
    effect_id = int(_core_setting(setting, "start_effect_id") or 0)

    if reaction_on and emoji:
        try:
            await Kenzo(
                functions.messages.SendReactionRequest(
                    peer=event.chat_id,
                    msg_id=event.id,
                    big=True,
                    reaction=[types.ReactionEmoji(emoticon=emoji)],
                    add_to_recent=False,
                )
            )
        except Exception as exc:
            logger.debug("Could not send reaction to message %s: %s", event.id, exc)

    send_kwargs = {
        "entity": event.sender_id,
        "message": welcome_text,
        "buttons": await bhome_buttons(event.sender_id, lang),
    }
    if reaction_on and effect_id:
        send_kwargs["message_effect_id"] = effect_id
    try:
        await Kenzo.send_message(**send_kwargs)
    except Exception as exc:
        # The effect id is admin-editable and Telegram rejects an unknown one,
        # which would fail the whole message: the user presses /start, nothing
        # arrives, and the keyboard already on their screen stays as it was.
        if "message_effect_id" not in send_kwargs:
            raise
        logger.warning("Welcome message with effect %s failed (%s) — resending without it", effect_id, exc)
        send_kwargs.pop("message_effect_id")
        await Kenzo.send_message(**send_kwargs)


async def handle_discount_start_param(user_id: int, param: str | None, *, notify: bool = True) -> bool:
    """Apply ``discount_CODE`` from /start and notify the user."""
    code = parse_discount_start_param(param)
    if not code:
        return False

    ok, result = await apply_sticky_discount(user_id, code)
    if notify:
        if ok and result in ("applied", "already_applied"):
            sticky = await get_sticky_discount(user_id)
            if sticky:
                message = format_sticky_applied_message(sticky)
                if result == "already_applied":
                    message = f"ℹ️ این کد تخفیف از قبل روی حساب شما فعال است.\n\n{message}"
                await Kenzo.send_message(entity=user_id, message=message, parse_mode="md")
        elif not ok:
            await Kenzo.send_message(entity=user_id, message=f"❌ {result}")

    if ok:
        logger.info("Sticky discount %s applied for user %s via start=%s", code, user_id, param)
    else:
        logger.info("Sticky discount %s rejected for user %s: %s", code, user_id, result)

    return True


async def prompt_channel_join(event: Message, lang: str) -> None:
    not_joined_channels = await get_not_joined_channels(event.sender_id)
    if not not_joined_channels:
        return

    await add_user(
        user_id=event.sender_id,
        step="start",
        time_s=Time_Date()["stamp"],
        language=lang,
    )
    await event.reply(
        CHANNEL_JOIN_MESSAGE.format(date=Time_Date()["mf"]),
        buttons=build_channel_join_buttons(not_joined_channels),
        parse_mode="html",
    )


async def start_command_filter(event: Message) -> bool:
    if event.is_channel:
        return False
    if await get_user_status(event.sender_id) == "ban":
        return False

    msg = event.message.text or event.message.message or ""
    if not msg.lower().startswith("/start") and extract_start_param(event) is None:
        return False

    param = extract_start_param(event)
    return not is_reserved_start_param(param)
