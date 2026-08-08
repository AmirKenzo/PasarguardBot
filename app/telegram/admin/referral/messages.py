"""Message handlers for admin referral system management."""

from telethon import Button, events
from telethon.tl.custom import Message

from app.db.crud.referral import ReferralManager
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

    if step == "change_referral_reward" and msg.isdigit():
        new_amount = int(msg)
        await referral_manager.settings_crud.update_settings(referral_reward_amount=new_amount)
        await event.respond(
            f"✅ مبلغ پاداش دعوت کننده به {new_amount:,} تومان تغییر یافت!",
            buttons=[[Button.inline("🔙 بازگشت به مدیریت دعوت", data="back_to_referral_management")]],
        )
        await set_step(event.sender_id, "panel")
        raise events.StopPropagation

    if step == "change_referral_bonus" and msg.isdigit():
        new_amount = int(msg)
        await referral_manager.settings_crud.update_settings(referral_bonus_amount=new_amount)
        await event.respond(
            f"✅ مبلغ هدیه دعوت شده به {new_amount:,} تومان تغییر یافت!",
            buttons=[[Button.inline("🔙 بازگشت به مدیریت دعوت", data="back_to_referral_management")]],
        )
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
