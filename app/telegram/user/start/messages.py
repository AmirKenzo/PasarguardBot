"""Message handlers for user start."""

from __future__ import annotations

from datetime import datetime

from telethon import events
from telethon.tl.custom import Message

from app import Kenzo
from app.db.crud.user import UserCRUD, add_user, clear_reactivatable_status
from app.logger import LogType, get_logger
from app.services.billing.referral import parse_referral_start_param
from app.telegram.keyboards.home import bhome_buttons
from app.telegram.shared.guards.channel_gate import (
    build_channel_join_buttons,
    extract_start_param,
    get_not_joined_channels,
)
from app.telegram.shared.start_params import is_documented_start_param
from app.telegram.shared.utils.help_download import download_app_file
from app.telegram.shared.utils.logging import send_log_message
from app.telegram.shared.utils.maintenance import bot_is_offline
from app.telegram.state import clear_user, get_step, set_step
from app.telegram.user.start import helpers
from app.utils.formatting.dates import Time_Date

logger = get_logger(__name__)


@bot_is_offline
async def start_command_handler(event: Message):
    param = extract_start_param(event)
    cleared_status = await clear_reactivatable_status(event.sender_id)
    if cleared_status:
        logger.info("User %s returned — cleared DB status %s", event.sender_id, cleared_status)
    lang = await helpers.get_user_lang(event.sender_id)
    info = await UserCRUD().read_user(event.sender_id)

    logger.info("handling /start with param=%s", param)
    existing_user = info

    referrer_id = parse_referral_start_param(param) if param else None

    if referrer_id and referrer_id != event.sender_id:
        referrer_user = await UserCRUD().read_user(referrer_id)
        if not referrer_user:
            logger.info("Referral start parameter references unknown user: %s", referrer_id)
        else:
            if existing_user:
                wlc = await helpers.fetch_welcome_text()
                await Kenzo.send_message(
                    entity=event.sender_id,
                    message=f"⚠️ شما قبلاً عضو ربات هستید و نمی‌توانید از سیستم دعوت استفاده کنید.\n\n{wlc}",
                    buttons=await bhome_buttons(event.sender_id, lang),
                )
                log_message = (
                    f"🚫 **تلاش عضویت در referral توسط کاربر موجود**\n\n"
                    f"👤 آیدی کاربر: `{event.sender_id}`\n"
                    f"👥 آیدی referrer: `{referrer_id}`\n"
                    f"📊 وضعیت کاربر: موجود در دیتابیس\n"
                    f"⏰ زمان: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
                await send_log_message(LogType.OTHER, message=log_message)
                raise events.StopPropagation

            await add_user(
                user_id=event.sender_id,
                step="start",
                time_s=Time_Date()["stamp"],
                language=lang,
            )
            existing_user = await UserCRUD().read_user(event.sender_id)

            success, _message = await UserCRUD().update_ref(event.sender_id, referrer_id)
            if success:
                from app.db.crud.referral import ReferralManager

                referral_manager = ReferralManager()
                settings = await referral_manager.get_referral_settings()
                bonus_amount = settings.referral_bonus_amount if settings else 40000

                not_joined_channels = await get_not_joined_channels(event.sender_id)

                if not_joined_channels:
                    await Kenzo.send_message(
                        entity=event.sender_id,
                        message=(
                            f"🎉 خوش آمدید! شما از طریق دعوت یکی از کاربران ما وارد شده‌اید.\n\n"
                            f"🎁 بعد از اولین خرید شما، مبلغ {bonus_amount:,} تومان به عنوان پاداش به حساب شما واریز خواهد شد!\n\n"
                            f"برای استفاده از ربات باید در کانال‌های زیر عضو شوید:\n"
                            f"<blockquote expandable>{Time_Date()['mf']}</blockquote>"
                        ),
                        buttons=build_channel_join_buttons(not_joined_channels),
                        parse_mode="html",
                    )
                else:
                    wlc = await helpers.fetch_welcome_text()
                    await Kenzo.send_message(
                        entity=event.sender_id,
                        message=(
                            f"🎉 خوش آمدید! شما از طریق دعوت یکی از کاربران ما وارد شده‌اید.\n\n"
                            f"🎁 بعد از اولین خرید شما، مبلغ {bonus_amount:,} تومان به عنوان پاداش به حساب شما واریز خواهد شد!\n\n"
                            f"{wlc}"
                        ),
                        buttons=await bhome_buttons(event.sender_id, lang),
                    )

                await Kenzo.send_message(
                    entity=referrer_id,
                    message=(
                        f"🎉 تبریک! یک کاربر جدید از طریق لینک دعوت شما وارد ربات شده است.\n\n"
                        f"👤 آیدی کاربر: {event.sender_id}\n"
                        f"💰 بعد از اولین خرید این کاربر، پاداش شما پرداخت خواهد شد."
                    ),
                )

                log_message = (
                    f"✅ **عضویت موفق در referral**\n\n"
                    f"👤 آیدی کاربر جدید: `{event.sender_id}`\n"
                    f"👥 آیدی referrer: `{referrer_id}`\n"
                    f"🎁 مبلغ پاداش: `{bonus_amount:,}` تومان\n"
                    f"⏰ زمان: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
                await send_log_message(LogType.OTHER, message=log_message)
                raise events.StopPropagation
    elif param and param.lower().startswith("ref_"):
        logger.info("Invalid referral start parameter received: %s", param)

    not_joined_channels = await get_not_joined_channels(event.sender_id)
    if not_joined_channels:
        await helpers.prompt_channel_join(event, lang)
        raise events.StopPropagation

    if not existing_user:
        await add_user(
            user_id=event.sender_id,
            step="start",
            time_s=Time_Date()["stamp"],
            language=lang,
        )

    await clear_user(event.sender_id)
    await set_step(event.sender_id, "start")
    welcome_text = await helpers.fetch_welcome_text()

    app_key = helpers.resolve_app_download_param(param)
    if app_key:
        await download_app_file(event, app_key)
    else:
        if helpers.parse_discount_start_param(param):
            await helpers.handle_discount_start_param(event.sender_id, param)
        elif param and not is_documented_start_param(param):
            logger.info("Unknown start param %r — showing welcome menu", param)
        await helpers.send_welcome_menu(event, welcome_text, lang)

    raise events.StopPropagation


async def _home_back_filter(event: Message) -> bool:
    if event.is_channel or not event.is_private:
        return False
    if await get_step(event.sender_id) == "ban":
        return False
    return (event.message.text or "").strip() == "🏠 بازگشت"


@bot_is_offline
async def home_back_handler(event: Message):
    lang = await helpers.get_user_lang(event.sender_id)
    await set_step(user_id=event.sender_id, step="home")
    await Kenzo.send_message(
        entity=event.sender_id,
        message="**شما برگشتید به صفحه اصلی**",
        buttons=await bhome_buttons(event.sender_id, lang),
    )
    raise events.StopPropagation


def register(client):
    client.add_event_handler(
        start_command_handler,
        events.NewMessage(incoming=True, func=helpers.start_command_filter),
    )
    client.add_event_handler(
        home_back_handler,
        events.NewMessage(incoming=True, func=_home_back_filter),
    )
