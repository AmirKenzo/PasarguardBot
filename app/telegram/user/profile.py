"""User profile: the profile menu with account and discount-code details."""

from telethon import events
from telethon.tl.custom import Message

from app import Kenzo
from app.db.crud.discount_codes import DiscountCodeManager
from app.db.crud.keyboards import get_button_text
from app.db.crud.user import UserCRUD
from app.services.billing.sticky_discount import format_profile_sticky_discount, get_sticky_discount
from app.telegram.keyboards.common import is_keyboard_config_step
from app.telegram.keyboards.home import home_back_button
from app.telegram.plugins import PluginContext
from app.telegram.shared.guards.channel_gate import ensure_channel_membership
from app.telegram.shared.url_presets import get_bot_username
from app.telegram.shared.utils.maintenance import bot_is_offline
from app.telegram.shared.utils.rate_limit import debounce_callback
from app.telegram.state import get_step, set_step
from app.utils.formatting.dates import Time_Date

MODULE_NAME = "user.profile"
MODULE_REQUIRED = True
MODULE_DESCRIPTION = "User profile flow"

BOT_LANGUAGE = "fa"

CALLBACK_BACK_TO_PROFILE = "back_to_profile"

STEP_MAIN = "main"

STEP_HOME = "home"

PROFILE_MENU_ALIASES = frozenset({"🙍 پروفایل من", "💼 حساب من", "🙍 My profile", "💼 My Account", "/mywallet"})

PHONE_NOT_REGISTERED = "ثبت نشده"

NO_DISCOUNT_CODE_TEXT = "🎁**کدتخفیف:** ❌`شما کدتخفیف اختصاصی ندارید`"

DATE_NOT_REGISTERED = "تاریخ ثبت نشده است."


def profile_buttons(info, settings):
    return []


def discount_code_text(discount_code) -> str:
    expiration = Time_Date(discount_code.expiration_date)
    usage_line = ""
    if not discount_code.is_public:
        usage_line = f"**🔢 تعداد استفاده:** `{discount_code.times_used}`**/**`{discount_code.usage_limit}`\n"
    return (
        "\n"
        f"**📌 کدتخفیف:** `{discount_code.code}`\n"
        f"**💸 درصد تخفیف:** `{discount_code.discount_percentage}%`\n"
        f"{usage_line}"
        f"**📋 نوع کد:** {'`🌍 عمومی 🌍`' if discount_code.is_public else '`💎 پرایوت 💎`'}\n"
        f"**⏳ تاریخ انقضا:** `{expiration['jf']} ({expiration['remaining_days']})`\n"
    )


def profile_message(
    user_id: int,
    info,
    date_label: str,
    discount_status: str,
) -> str:
    return (
        f"**👤 شناسه کاربری:** `{user_id}`\n"
        f"**👥 تعداد زیرمجموعه ها:**  `{info.invite:,}`\n"
        f"**💰 موجودی:** `{info.amount:,.0f}` تومان\n"
        f"**📞 شماره تلفن:** `{info.number}`\n"
        f"**🕒 تاریخ عضویت:** `{date_label}`\n"
        f"{discount_status}\n"
    )


async def _build_discount_status(user_id: int) -> str:
    sticky = await get_sticky_discount(user_id)
    if sticky and sticky.is_public:
        bot_username = await get_bot_username(Kenzo)
        return format_profile_sticky_discount(sticky, bot_username)

    discount_code_status = await DiscountCodeManager().get_code_whith_user_id(user_id)
    if discount_code_status is False:
        return NO_DISCOUNT_CODE_TEXT
    return discount_code_text(discount_code_status)


async def _build_profile_message(user_id: int, info) -> str:
    date_message = Time_Date(info.time_s) if info.time_s else {"jf": DATE_NOT_REGISTERED}
    discount_status = await _build_discount_status(user_id)
    if info.number is None:
        info.number = PHONE_NOT_REGISTERED
    return profile_message(
        user_id,
        info,
        date_message["jf"],
        discount_status,
    )


async def menu_profile_filter(event):
    if event.is_channel:
        return False
    if is_keyboard_config_step(await get_step(event.sender_id)):
        return False
    msg = event.message.message or ""
    profile_text = await get_button_text("bt.menu_profile", "🙍 پروفایل من")
    return msg in PROFILE_MENU_ALIASES | {profile_text}


@bot_is_offline
async def menu_profile(event: Message):
    if not await ensure_channel_membership(event):
        raise events.StopPropagation

    user_id = event.sender_id
    info = await UserCRUD().read_user(user_id)
    profile_message = await _build_profile_message(user_id, info)
    buttons = profile_buttons(info, None)

    await event.respond(profile_message, buttons=buttons or None)
    raise events.StopPropagation


@bot_is_offline
@debounce_callback()
async def callback_back_to_profile(event: events.CallbackQuery.Event):
    user_id = event.sender_id
    await set_step(user_id=user_id, step=STEP_MAIN)
    info = await UserCRUD().read_user(user_id)
    profile_message = await _build_profile_message(user_id, info)
    await event.edit(profile_message, buttons=[[home_back_button()]])


def setup(ctx: PluginContext) -> None:
    ctx.add_event_handler(
        menu_profile,
        events.NewMessage(incoming=True, func=menu_profile_filter),
    )
    ctx.add_event_handler(
        callback_back_to_profile,
        events.CallbackQuery(data=CALLBACK_BACK_TO_PROFILE),
    )
