"""Message handlers for admin referral system management."""

from telethon import Button, events
from telethon.tl.custom import Message

from app.db.crud.referral import ReferralManager
from app.services.billing.referral_rewards import REWARD_PERCENT_MAX, REWARD_PERCENT_MIN
from app.telegram.admin.referral import service, states
from app.telegram.state import get_step, set_step
from config import ADMIN_ID


async def _referral_admin_message_filter(event: Message) -> bool:
    if event.sender_id not in ADMIN_ID:
        return False
    msg = (event.message.text or "").strip()
    if msg == states.REFERRAL_MENU_MESSAGE:
        return True
    step = await get_step(event.sender_id)
    return step in states.REFERRAL_ADMIN_STEPS


async def message_handler_referral_admin(event: Message):
    msg = (event.message.text or "").strip()
    step = await get_step(event.sender_id)
    referral_manager = ReferralManager()

    if msg == states.REFERRAL_MENU_MESSAGE:
        settings = await referral_manager.get_referral_settings()

        if settings:
            await event.respond(
                service.referral_management_message(settings),
                buttons=service.referral_management_buttons(settings),
            )
        else:
            await event.respond("❌ خطا در دریافت تنظیمات سیستم دعوت")
        raise events.StopPropagation

    back = [[Button.inline("🔙 بازگشت به مدیریت دعوت", data="back_to_referral_management")]]

    if step in service.PERCENT_STEPS:
        side = service.PERCENT_STEPS[step]
        if not msg.isdigit() or not REWARD_PERCENT_MIN <= int(msg) <= REWARD_PERCENT_MAX:
            await event.respond(f"❌ یک عدد بین {REWARD_PERCENT_MIN} تا {REWARD_PERCENT_MAX} بفرستید.")
            raise events.StopPropagation
        percent = int(msg)
        await referral_manager.settings_crud.update_settings(**{f"referral_{side}_percent": percent})
        await event.respond(f"✅ درصد {service.SIDE_LABELS[side]} روی {percent}٪ تنظیم شد!", buttons=back)
        await set_step(event.sender_id, "panel")
        raise events.StopPropagation

    if step in service.MAX_STEPS:
        side = service.MAX_STEPS[step]
        if not msg.isdigit():
            await event.respond("❌ فقط عدد بفرستید (به تومان؛ 0 یعنی بدون سقف).")
            raise events.StopPropagation
        cap = int(msg)
        cap_text = "برداشته شد" if cap == 0 else f"روی {cap:,} تومان تنظیم شد"
        await referral_manager.settings_crud.update_settings(**{f"referral_{side}_max": cap})
        await event.respond(f"✅ سقف {service.SIDE_LABELS[side]} {cap_text}!", buttons=back)
        await set_step(event.sender_id, "panel")
        raise events.StopPropagation

    if step in service.FIXED_STEPS:
        side = service.FIXED_STEPS[step]
        if not msg.isdigit():
            await event.respond("❌ فقط عدد بفرستید (به تومان؛ 0 یعنی هیچ).")
            raise events.StopPropagation
        amount = int(msg)
        await referral_manager.settings_crud.update_settings(**{f"referral_{side}_amount": amount})
        await event.respond(f"✅ مبلغ {service.SIDE_LABELS[side]} به {amount:,} تومان تغییر یافت!", buttons=back)
        await set_step(event.sender_id, "panel")
        raise events.StopPropagation

    if step == "change_referral_banner" and msg:
        await referral_manager.settings_crud.update_settings(referral_banner_text=msg)
        await event.respond(
            "✅ متن بنر به‌روزرسانی شد!",
            buttons=[[Button.inline("🔙 بازگشت به مدیریت دعوت", data="back_to_referral_management")]],
        )
        await set_step(event.sender_id, "panel")
        raise events.StopPropagation


def register(client):
    client.add_event_handler(
        message_handler_referral_admin,
        events.NewMessage(incoming=True, from_users=ADMIN_ID, func=_referral_admin_message_filter),
    )
