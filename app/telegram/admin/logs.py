"""Admin log management: choose the channel or topic each log type is sent to."""

from telethon import events
from telethon.tl.custom import Message

from app import Kenzo
from app.db.crud.log_channels import LogChannelManager
from app.logger import get_logger
from app.telegram.keyboards.admin import Panel_Admin_Buttons
from app.telegram.keyboards.common import glass_inline_button
from app.telegram.plugins import PluginContext
from app.telegram.shared.utils.channels import parse_telegram_message_link
from app.telegram.state import clear_user, get_data, get_step, set_data, set_step
from config import ADMIN_ID

MODULE_NAME = "admin.logs"
MODULE_REQUIRED = True
MODULE_DESCRIPTION = "Admin log destination management"

LOG_MANAGEMENT_STEP = "LogManagement"

SHOW_LOG_STATUS_STEP = "ShowLogStatus"

SET_LOG_CHANNEL_PREFIX = "SetLogChannel_"

SET_LOG_SUPERGROUP_PREFIX = "SetLogSupergroup_"

SET_LOG_TOPIC_PREFIX = "SetLogTopic_"

LOG_INPUT_STEP_PREFIXES = (
    SET_LOG_CHANNEL_PREFIX,
    SET_LOG_SUPERGROUP_PREFIX,
    SET_LOG_TOPIC_PREFIX,
)

SET_ALL_LOG_TYPE = "all"

BACK_TO_LOG_MANAGEMENT = "BackToLogManagement"

BACK_TO_ADMIN_PANEL = "LogBackToAdmin"

LOG_SHOW_STATUS = "log_show_status"

LOG_SET_ALL = "log_set_all"

LOG_TYPE_PREFIX = "log_type:"

ALL_LOG_TYPES: tuple[tuple[str, str], ...] = (
    ("manual_card", "💳 کارت به کارت دستی"),
    ("crypto", "💱 واریزی ارزی"),
    ("reseller", "🏢 لاگ نمایندگی‌ها"),
    ("referral", "🎁 دعوت دوستان و برداشت‌ها"),
    ("other", "📋 سایر لاگ‌ها"),
    ("backup", "🗄 بکاپ ربات"),
    ("app_files", "📦 کانال آپدیت برنامه‌ها"),
    ("purchase", "🛍 گزارش خرید (کانال عمومی)"),
)


def main_menu_buttons() -> list:
    rows = []
    log_types = list(ALL_LOG_TYPES)
    for i in range(0, len(log_types), 2):
        pair = log_types[i : i + 2]
        rows.append([glass_inline_button(label, data=f"{LOG_TYPE_PREFIX}{key}") for key, label in pair])
    rows.append([glass_inline_button("⚡ ست همه لاگ‌ها با یک آیدی", data=LOG_SET_ALL)])
    rows.append([glass_inline_button("📊 وضعیت لاگ‌ها", data=LOG_SHOW_STATUS)])
    rows.append([glass_inline_button("🔙 بازگشت به پنل", data=BACK_TO_ADMIN_PANEL)])
    return rows


def back_rows() -> list:
    return [[glass_inline_button("🔙 بازگشت", data=BACK_TO_LOG_MANAGEMENT)]]


def back_button() -> list:
    return [glass_inline_button("🔙 بازگشت", data=BACK_TO_LOG_MANAGEMENT)]


def back_to_management_button() -> list:
    return [glass_inline_button("🔙 بازگشت به مدیریت لاگ‌ها", data=BACK_TO_LOG_MANAGEMENT)]


def destination_type_rows(log_type: str) -> list:
    return [
        [glass_inline_button("📢 کانال", data=f"log_dest_channel:{log_type}")],
        [glass_inline_button("👥 سوپرگروه با تایپک", data=f"log_dest_supergroup:{log_type}")],
        [glass_inline_button("🔙 بازگشت", data=BACK_TO_LOG_MANAGEMENT)],
    ]


def set_all_destination_rows() -> list:
    return destination_type_rows(SET_ALL_LOG_TYPE)


LOG_ENTRY_MESSAGE = "📝 مدیریت لاگ‌ها"

LOG_TYPE_LABELS = dict(ALL_LOG_TYPES)


def log_type_label(log_type: str) -> str:
    if log_type == SET_ALL_LOG_TYPE:
        return "همه لاگ‌ها"
    return LOG_TYPE_LABELS.get(log_type, log_type)


LOG_MANAGEMENT_TEXT = (
    "📝 **مدیریت لاگ‌ها**\n\n"
    "از این بخش می‌توانید کانال‌ها و گروه‌های مقصد برای ارسال لاگ‌ها را تنظیم کنید.\n\n"
    "برای تنظیم سریع همه لاگ‌ها با یک آیدی، از گزینه **⚡ ست همه لاگ‌ها با یک آیدی** استفاده کنید."
)

SET_ALL_DESTINATION_TEXT = (
    "⚡ **ست همه لاگ‌ها با یک آیدی**\n\n"
    "با این گزینه یک مقصد برای **همه** انواع لاگ تنظیم می‌شود.\n"
    "لطفاً نوع مقصد را انتخاب کنید:"
)


def destination_menu_text(log_type: str) -> str:
    label = log_type_label(log_type)
    return f"**{label}**\n\nلطفاً نوع مقصد را انتخاب کنید:"


EMPTY_LOG_STATUS_TEXT = "📊 **وضعیت لاگ‌ها**\n\n❌ هیچ لاگی تنظیم نشده است."

LOG_STATUS_HEADER = "📊 **وضعیت لاگ‌ها**\n\n"

INVALID_NUMERIC_ID_TEXT = "❌ لطفاً آیدی عددی معتبر ارسال کنید!"

INVALID_GROUP_OR_TOPIC_TEXT = (
    "❌ لطفاً یکی از موارد زیر را ارسال کنید:\n\n"
    "• لینک یک پیام از تایپک (مثل: https://t.me/c/3210435570/2/10122)\n"
    "• آیدی عددی گروه (مثل: -1001234567890)"
)

INVALID_TOPIC_TEXT = (
    "❌ لطفاً یکی از موارد زیر را ارسال کنید:\n\n"
    "• لینک یک پیام از تایپک (مثل: https://t.me/c/3210435570/2/10122)\n"
    "• آیدی عددی تایپک"
)

MISSING_CHAT_ID_TEXT = "❌ خطا: آیدی گروه یافت نشد. لطفاً دوباره شروع کنید."


def channel_setup_text(log_type: str) -> str:
    label = log_type_label(log_type)
    if log_type == SET_ALL_LOG_TYPE:
        return (
            f"📢 **تنظیم کانال برای {label}**\n\n"
            "لطفاً آیدی عددی کانال را ارسال کنید.\n"
            "این آیدی برای **همه** انواع لاگ ذخیره می‌شود.\n\n"
            "⚠️ **نکته:** آیدی کانال معمولاً با علامت منفی شروع می‌شود (مثل: -1001234567890)"
        )
    return (
        f"📢 **تنظیم کانال برای {label}**\n\n"
        "لطفاً آیدی عددی کانال را ارسال کنید.\n\n"
        "⚠️ **نکته:** آیدی کانال معمولاً با علامت منفی شروع می‌شود (مثل: -1001234567890)"
    )


def supergroup_setup_text(log_type: str) -> str:
    label = log_type_label(log_type)
    if log_type == SET_ALL_LOG_TYPE:
        return (
            f"👥 **تنظیم سوپرگروه با تایپک برای {label}**\n\n"
            "لطفاً آیدی عددی گروه یا لینک پیام تایپک را ارسال کنید.\n"
            "این مقصد برای **همه** انواع لاگ ذخیره می‌شود.\n\n"
            "⚠️ **نکته:** آیدی گروه معمولاً با علامت منفی شروع می‌شود (مثل: -1001234567890)"
        )
    return (
        f"👥 **تنظیم سوپرگروه با تایپک برای {label}**\n\n"
        "لطفاً آیدی عددی گروه را ارسال کنید.\n\n"
        "⚠️ **نکته:** آیدی گروه معمولاً با علامت منفی شروع می‌شود (مثل: -1001234567890)"
    )


def status_line(log) -> str:
    label = log_type_label(log.log_type)
    if log.is_active:
        if log.topic_id:
            return f"✅ **{label}**: سوپرگروه `{log.chat_id}` (تایپک: `{log.topic_id}`)\n"
        return f"✅ **{label}**: کانال `{log.chat_id}`\n"
    return f"❌ **{label}**: غیرفعال\n"


def test_success_text(log_type: str) -> str:
    label = log_type_label(log_type)
    return f"✅ لاگ {label} با موفقیت ست شد!\n\nاین پیام تست است."


def test_all_success_text() -> str:
    return "✅ **همه لاگ‌ها** با موفقیت ست شدند!\n\nاین پیام تست است."


def channel_configured_text(log_type: str, chat_id: int) -> str:
    label = log_type_label(log_type)
    if log_type == SET_ALL_LOG_TYPE:
        return f"✅ کانال برای **همه لاگ‌ها** با موفقیت تنظیم شد!\nآیدی کانال: `{chat_id}`\n\nپیام تست ارسال شد."
    return f"✅ کانال لاگ {label} با موفقیت تنظیم شد!\nآیدی کانال: `{chat_id}`\n\nپیام تست ارسال شد."


def channel_test_error_text(error: Exception) -> str:
    return f"❌ خطا در ارسال پیام تست به کانال!\nلطفاً مطمئن شوید که ربات در کانال عضو است.\n\nخطا: {error!s}"


def supergroup_configured_text(log_type: str, chat_id, topic_id) -> str:
    label = log_type_label(log_type)
    if log_type == SET_ALL_LOG_TYPE:
        return (
            f"✅ سوپرگروه برای **همه لاگ‌ها** با موفقیت تنظیم شد!\n"
            f"آیدی گروه: `{chat_id}`\n"
            f"آیدی تایپک: `{topic_id}`\n\n"
            "پیام تست ارسال شد."
        )
    return (
        f"✅ سوپرگروه لاگ {label} با موفقیت تنظیم شد!\n"
        f"آیدی گروه: `{chat_id}`\n"
        f"آیدی تایپک: `{topic_id}`\n\n"
        "پیام تست ارسال شد."
    )


def supergroup_configured_warning_text(log_type: str, chat_id, topic_id, error: Exception) -> str:
    label = log_type_label(log_type)
    if log_type == SET_ALL_LOG_TYPE:
        return (
            f"✅ سوپرگروه برای **همه لاگ‌ها** با موفقیت تنظیم شد!\n"
            f"آیدی گروه: `{chat_id}`\n"
            f"آیدی تایپک: `{topic_id}`\n\n"
            f"⚠️ خطا در ارسال پیام تست: {error!s}"
        )
    return (
        f"✅ سوپرگروه لاگ {label} با موفقیت تنظیم شد!\n"
        f"آیدی گروه: `{chat_id}`\n"
        f"آیدی تایپک: `{topic_id}`\n\n"
        f"⚠️ خطا در ارسال پیام تست: {error!s}"
    )


def log_setup_error_text(error: Exception) -> str:
    return f"❌ خطا در تنظیم لاگ!\nلطفاً مطمئن شوید که ربات در گروه عضو است و تایپک درست است.\n\nخطا: {error!s}"


def topic_prompt_text(log_type: str) -> str:
    label = log_type_label(log_type)
    extra = "\nاین تایپک برای **همه** انواع لاگ ذخیره می‌شود." if log_type == SET_ALL_LOG_TYPE else ""
    return (
        f"👥 **تنظیم تایپک برای {label}**\n\n"
        f"حالا آیدی عددی تایپک را ارسال کنید.{extra}\n\n"
        "⚠️ **نکته:** می‌توانید لینک یک پیام از تایپک را ارسال کنید یا آیدی عددی تایپک را."
    )


def topic_test_fallback_text(topic_id, log_type: str) -> str:
    label = log_type_label(log_type)
    if log_type == SET_ALL_LOG_TYPE:
        return f"📌 **تایپک: {topic_id}**\n\n✅ **همه لاگ‌ها** با موفقیت ست شدند!\n\nاین پیام تست است."
    return f"📌 **تایپک: {topic_id}**\n\n✅ لاگ {label} با موفقیت ست شد!\n\nاین پیام تست است."


def log_callback_filter(event: events.CallbackQuery.Event) -> bool:
    if event.sender_id not in ADMIN_ID:
        return False
    data = event.data.decode("utf-8")
    if data in {
        BACK_TO_LOG_MANAGEMENT,
        BACK_TO_ADMIN_PANEL,
        LOG_SHOW_STATUS,
        LOG_SET_ALL,
    }:
        return True
    return bool(
        data.startswith(LOG_TYPE_PREFIX)
        or data.startswith("log_dest_channel:")
        or data.startswith("log_dest_supergroup:")
    )


async def _show_log_management_menu(event: events.CallbackQuery.Event) -> None:
    await set_step(user_id=event.sender_id, step=LOG_MANAGEMENT_STEP)
    await event.edit(
        LOG_MANAGEMENT_TEXT,
        buttons=main_menu_buttons(),
    )


async def callback_log_admin(event: events.CallbackQuery.Event):
    data = event.data.decode("utf-8")

    if data == BACK_TO_LOG_MANAGEMENT:
        await _show_log_management_menu(event)

    elif data == BACK_TO_ADMIN_PANEL:
        await set_step(user_id=event.sender_id, step="panel")
        username = event.sender.username if event.sender.username else "بدون نام کاربری"
        await event.edit(
            f"**🌺به پنل مدیریت خوش آمدید.**\nایدی عددی شما: `{event.sender_id}`\nنام کاربری شما: @{username}\n",
            buttons=Panel_Admin_Buttons,
        )

    elif data == LOG_SHOW_STATUS:
        await set_step(user_id=event.sender_id, step=SHOW_LOG_STATUS_STEP)
        all_logs = await LogChannelManager().get_all_log_channels()
        if not all_logs:
            await event.edit(
                EMPTY_LOG_STATUS_TEXT,
                buttons=back_rows(),
            )
        else:
            status_text = LOG_STATUS_HEADER
            for log in all_logs:
                status_text += status_line(log)
            await event.edit(
                status_text,
                buttons=back_rows(),
            )

    elif data == LOG_SET_ALL:
        await set_step(user_id=event.sender_id, step=LOG_MANAGEMENT_STEP)
        await event.edit(
            SET_ALL_DESTINATION_TEXT,
            buttons=set_all_destination_rows(),
        )

    elif data.startswith(LOG_TYPE_PREFIX):
        log_type = data.split(":", 1)[1]
        await set_step(user_id=event.sender_id, step=LOG_MANAGEMENT_STEP)
        await event.edit(
            destination_menu_text(log_type),
            buttons=destination_type_rows(log_type),
        )

    elif data.startswith("log_dest_channel:"):
        log_type = data.split(":")[1]
        await set_step(user_id=event.sender_id, step=f"{SET_LOG_CHANNEL_PREFIX}{log_type}")
        await event.edit(
            channel_setup_text(log_type),
            buttons=back_rows(),
        )

    elif data.startswith("log_dest_supergroup:"):
        log_type = data.split(":")[1]
        await set_step(user_id=event.sender_id, step=f"{SET_LOG_SUPERGROUP_PREFIX}{log_type}")
        await event.edit(
            supergroup_setup_text(log_type),
            buttons=back_rows(),
        )

    raise events.StopPropagation


logger = get_logger(__name__)


def _log_types_for(log_type: str) -> list[str]:
    if log_type == SET_ALL_LOG_TYPE:
        return [key for key, _ in ALL_LOG_TYPES]
    return [log_type]


async def _save_log_destination(
    log_type: str,
    *,
    destination_type: str,
    chat_id: int,
    topic_id: int | None = None,
) -> None:
    log_manager = LogChannelManager()
    for item_type in _log_types_for(log_type):
        description = f"کانال لاگ {item_type}" if destination_type == "channel" else f"سوپرگروه لاگ {item_type}"
        await log_manager.create_or_update_log_channel(
            log_type=item_type,
            destination_type=destination_type,
            chat_id=chat_id,
            topic_id=topic_id,
            description=description,
        )


async def _send_test_message(log_type: str, chat_id: int, topic_id: int | None = None) -> None:
    message = test_all_success_text() if log_type == SET_ALL_LOG_TYPE else test_success_text(log_type)
    if topic_id is not None:
        await Kenzo.send_message(entity=chat_id, message=message, reply_to=topic_id)
    else:
        await Kenzo.send_message(entity=chat_id, message=message)


async def _log_admin_message_filter(event: Message) -> bool:
    if event.sender_id not in ADMIN_ID:
        return False
    msg = (event.message.text or "").strip()
    if msg == LOG_ENTRY_MESSAGE:
        return True
    step = (await get_step(event.sender_id)) or ""
    return bool(step.startswith(LOG_INPUT_STEP_PREFIXES) and msg)


async def message_handler_log_admin(event: Message):
    msg = (event.message.text or "").strip()
    step = (await get_step(event.sender_id)) or ""

    if msg == LOG_ENTRY_MESSAGE:
        await set_step(user_id=event.sender_id, step=LOG_MANAGEMENT_STEP)
        await event.respond(
            LOG_MANAGEMENT_TEXT,
            buttons=main_menu_buttons(),
        )
        raise events.StopPropagation

    if step.startswith(SET_LOG_CHANNEL_PREFIX) and msg:
        if msg.lstrip("-").isdigit():
            log_type = step.replace(SET_LOG_CHANNEL_PREFIX, "")
            chat_id = int(msg)
            await _save_log_destination(
                log_type,
                destination_type="channel",
                chat_id=chat_id,
            )
            try:
                await _send_test_message(log_type, chat_id)
                await event.respond(
                    channel_configured_text(log_type, chat_id),
                    buttons=back_to_management_button(),
                )
                await set_step(event.sender_id, LOG_MANAGEMENT_STEP)
            except Exception as e:
                await event.respond(
                    channel_test_error_text(e),
                    buttons=back_button(),
                )
        else:
            await event.respond(INVALID_NUMERIC_ID_TEXT)
        raise events.StopPropagation

    if step.startswith(SET_LOG_SUPERGROUP_PREFIX) and msg:
        log_type = step.replace(SET_LOG_SUPERGROUP_PREFIX, "")
        parsed = parse_telegram_message_link(msg)
        if parsed:
            chat_id, topic_id = parsed
            try:
                await _save_log_destination(
                    log_type,
                    destination_type="supergroup",
                    chat_id=chat_id,
                    topic_id=topic_id,
                )
                try:
                    await _send_test_message(log_type, chat_id, topic_id)
                    await event.respond(
                        supergroup_configured_text(log_type, chat_id, topic_id),
                        buttons=back_to_management_button(),
                    )
                    await set_step(event.sender_id, LOG_MANAGEMENT_STEP)
                except Exception as e:
                    await event.respond(
                        supergroup_configured_warning_text(log_type, chat_id, topic_id, e),
                        buttons=back_to_management_button(),
                    )
                    await set_step(event.sender_id, LOG_MANAGEMENT_STEP)
            except Exception as e:
                await event.respond(
                    log_setup_error_text(e),
                    buttons=back_button(),
                )
        elif msg.lstrip("-").isdigit():
            chat_id = int(msg)
            await set_step(event.sender_id, f"{SET_LOG_TOPIC_PREFIX}{log_type}")
            await set_data(event.sender_id, "supergroup_chat_id", chat_id)
            await event.respond(
                topic_prompt_text(log_type),
                buttons=back_button(),
            )
        else:
            await event.respond(
                INVALID_GROUP_OR_TOPIC_TEXT,
                buttons=back_button(),
            )
        raise events.StopPropagation

    if step.startswith(SET_LOG_TOPIC_PREFIX) and msg:
        log_type = step.replace(SET_LOG_TOPIC_PREFIX, "")
        parsed = parse_telegram_message_link(msg)
        if parsed:
            chat_id_from_link, topic_id = parsed
            chat_id = await get_data(event.sender_id, "supergroup_chat_id")
            if not chat_id:
                chat_id = chat_id_from_link
        elif msg.lstrip("-").isdigit():
            topic_id = int(msg)
            chat_id = await get_data(event.sender_id, "supergroup_chat_id")
        else:
            await event.respond(
                INVALID_TOPIC_TEXT,
                buttons=back_button(),
            )
            raise events.StopPropagation

        if not chat_id:
            await event.respond(
                MISSING_CHAT_ID_TEXT,
                buttons=back_button(),
            )
            raise events.StopPropagation

        try:
            await _save_log_destination(
                log_type,
                destination_type="supergroup",
                chat_id=int(chat_id),
                topic_id=int(topic_id),
            )
            try:
                await _send_test_message(log_type, int(chat_id), int(topic_id))
            except Exception as topic_error:
                logger.warning("Failed to send to topic %s: %s", topic_id, topic_error)
                await Kenzo.send_message(
                    entity=int(chat_id),
                    message=topic_test_fallback_text(topic_id, log_type),
                )

            await clear_user(event.sender_id)
            await event.respond(
                supergroup_configured_text(log_type, chat_id, topic_id),
                buttons=back_to_management_button(),
            )
            await set_step(event.sender_id, LOG_MANAGEMENT_STEP)
        except Exception as e:
            await event.respond(
                log_setup_error_text(e),
                buttons=back_button(),
            )
        raise events.StopPropagation


def setup(kenzo: PluginContext) -> None:
    kenzo.add_event_handler(
        message_handler_log_admin,
        events.NewMessage(incoming=True, from_users=ADMIN_ID, func=_log_admin_message_filter),
    )
    kenzo.add_event_handler(callback_log_admin, events.CallbackQuery(func=log_callback_filter))
