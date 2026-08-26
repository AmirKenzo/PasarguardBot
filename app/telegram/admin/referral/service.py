"""Helper utilities for admin referral system management."""

from __future__ import annotations

from telethon import Button
from telethon.tl.types import KeyboardInlineButtonRow, ReplyInlineMarkup

from app.db.crud.referral import ReferralManager
from app.db.crud.user import UserCRUD
from app.services.billing.referral import build_referral_start_param
from app.telegram.keyboards.balance import balance_back_home_button
from app.telegram.keyboards.common import styled_copy_button
from app.telegram.state import set_step


def referral_management_message(settings) -> str:
    status = "🟢 فعال" if settings.referral_enabled else "🔴 غیرفعال"
    return (
        f"🎁 **مدیریت سیستم دعوت دوستان**\n\n"
        f"📊 **وضعیت سیستم:** {status}\n"
        f"💰 **مبلغ پاداش دعوت کننده:** `{settings.referral_reward_amount:,}` تومان\n"
        f"🎁 **مبلغ هدیه دعوت شده:** `{settings.referral_bonus_amount:,}` تومان\n\n"
        f"**تنظیمات فعلی:**\n"
        f"• سیستم دعوت: {'فعال' if settings.referral_enabled else 'غیرفعال'}\n"
        f"• پاداش دعوت کننده: {settings.referral_reward_amount:,} تومان\n"
        f"• هدیه دعوت شده: {settings.referral_bonus_amount:,} تومان\n\n"
        f"برای تغییر تنظیمات از دکمه‌های زیر استفاده کنید:"
    )


def referral_management_buttons(settings) -> list:
    return [
        [
            Button.inline(
                f"🔄 {'غیرفعال کردن' if settings.referral_enabled else 'فعال کردن'} سیستم",
                data="toggle_referral_system",
            )
        ],
        [Button.inline("💰 تغییر مبلغ پاداش دعوت کننده", data="change_referral_reward")],
        [Button.inline("🎁 تغییر مبلغ هدیه دعوت شده", data="change_referral_bonus")],
        [Button.inline("🎨 تغییر متن بنر", data="change_referral_banner")],
        [Button.inline("📊 آمار سیستم دعوت", data="referral_stats")],
        [Button.inline("🔙 بازگشت به پنل", data="back_to_admin_panel")],
    ]


async def handle_referral_callbacks(event, data):
    """Handle referral system callback queries."""

    referral_manager = ReferralManager()

    if data == "toggle_referral_system":
        settings = await referral_manager.get_referral_settings()
        if settings:
            new_status = not settings.referral_enabled
            await referral_manager.settings_crud.update_settings(referral_enabled=new_status)
            status_text = "فعال" if new_status else "غیرفعال"
            await event.edit(
                f"✅ سیستم دعوت دوستان {status_text} شد!",
                buttons=[[Button.inline("🔙 بازگشت به مدیریت دعوت", data="back_to_referral_management")]],
            )
        else:
            await event.edit("❌ خطا در تغییر وضعیت سیستم دعوت")

    elif data == "change_referral_reward":
        await event.edit(
            "💰 **تغییر مبلغ پاداش دعوت کننده**\n\nلطفاً مبلغ جدید پاداش دعوت کننده را ارسال کنید (به تومان):",
            buttons=[[Button.inline("🔙 بازگشت", data="back_to_referral_management")]],
        )
        await set_step(event.sender_id, "change_referral_reward")

    elif data == "change_referral_bonus":
        await event.edit(
            "🎁 **تغییر مبلغ هدیه دعوت شده**\n\nلطفاً مبلغ جدید هدیه دعوت شده را ارسال کنید (به تومان):",
            buttons=[[Button.inline("🔙 بازگشت", data="back_to_referral_management")]],
        )
        await set_step(event.sender_id, "change_referral_bonus")

    elif data == "change_referral_banner":
        await event.edit(
            "🎨 **تغییر متن بنر**\n\nلطفاً متن جدید بنر را ارسال کنید.\n\n💡 **نکته:** می‌توانید از پلیس‌هولدر  های زیر استفاده کنید:\n• `{referral_link}` - لینک دعوت\n• `{referral_reward_amount}` - مبلغ پاداش دعوت کننده\n• `{referral_bonus_amount}` - مبلغ هدیه دعوت شده",
            buttons=[[Button.inline("🔙 بازگشت", data="back_to_referral_management")]],
        )
        await set_step(event.sender_id, "change_referral_banner")

    elif data == "referral_stats":
        total_rewards = await referral_manager.reward_crud.get_total_referral_earnings(event.sender_id)
        total_referrals = await referral_manager.reward_crud.get_referral_count(event.sender_id)

        stats_text = (
            f"📊 **آمار سیستم دعوت دوستان**\n\n"
            f"💰 **کل درآمد از دعوت:** `{total_rewards:,}` تومان\n"
            f"👥 **تعداد دعوت‌های موفق:** `{total_referrals:,}` نفر\n\n"
            f"**نکته:** این آمار فقط برای شما نمایش داده می‌شود."
        )

        await event.edit(stats_text, buttons=[[Button.inline("🔙 بازگشت", data="back_to_referral_management")]])

    elif data == "back_to_referral_management":
        settings = await referral_manager.get_referral_settings()
        if settings:
            await event.edit(
                referral_management_message(settings),
                buttons=referral_management_buttons(settings),
            )
        else:
            await event.edit("❌ خطا در دریافت تنظیمات سیستم دعوت")

    elif data == "referral_invite_friends":
        settings = await referral_manager.get_referral_settings()
        if not settings or not settings.referral_enabled:
            await event.edit(
                "❌ سیستم دعوت دوستان در حال حاضر غیرفعال است.",
                buttons=[[Button.inline("🔙 بازگشت", data="back_to_balance")]],
            )
            return

        bot_username = (await event.client.get_me()).username
        referral_param = build_referral_start_param(event.sender_id)
        referral_link = f"https://t.me/{bot_username}?start={referral_param}"

        banner_text = (
            settings.referral_banner_text
            or "• انتقال حجم باقیمانده به دوره بعدی\n• شروع قیمت از 10 هزار تومان\n• فعال روی تمامی اپراتورها\n• قابل استفاده در 2 دستگاه\n• امکان تغییر سرور و لوکیشن\n• امکان تغییر لینک و پروتکل\n• تنوع کشور و موقعیت سرور\n• آیفون / اندروید / ویندوز / مک\n• پشتیبانی از ChatGPT و Spotify\n\n🔥 {referral_link}\n\n✅ ربات رو با لینک بالا استارت کن و پس از ثبت نام اعتبار رایگان هدیه بگیر !\n\n👆🏻 بنر و لینک ریفرال اختصاصی شما برای دعوت دیگران\n\n❕پس از عضویت و خرید، مبلغ هدیه به صورت خودکار برای هردو طرف در کیف پول افزوده میشود."
        )

        referral_message = banner_text.replace("{referral_link}", referral_link)
        referral_message = referral_message.replace("{referral_reward_amount}", f"{settings.referral_reward_amount:,}")
        referral_message = referral_message.replace("{referral_bonus_amount}", f"{settings.referral_bonus_amount:,}")

        copy_button = styled_copy_button("📋 کپی لینک دعوت", referral_link)

        stats_button = Button.inline("📊 آمار دعوت‌های من", data="my_referral_stats")
        back_home_button = await balance_back_home_button()

        custom_markup = ReplyInlineMarkup(
            [
                KeyboardInlineButtonRow([copy_button]),
                KeyboardInlineButtonRow([stats_button]),
                KeyboardInlineButtonRow([back_home_button]),
            ]
        )

        await event.edit(referral_message, buttons=custom_markup)

    elif data == "my_referral_stats":
        user_stats = await referral_manager.get_user_referral_stats(event.sender_id)
        settings = await referral_manager.get_referral_settings()

        user_crud = UserCRUD()
        referred_users = await user_crud.get_referred_users(event.sender_id)

        pending_users = 0
        completed_users = 0

        for referred_user in referred_users:
            if referred_user.amount and referred_user.amount > 0:
                completed_users += 1
            else:
                pending_users += 1

        stats_message = f"""📊 **آمار تفصیلی دعوت شما:**

👥 **تعداد دعوت‌های موفق:** {user_stats["referral_count"]} نفر
💰 **کل درآمد از دعوت:** {user_stats["total_earnings"]:,} تومان
🎁 **پاداش هر دعوت:** {settings.referral_reward_amount:,} تومان
💝 **هدیه دعوت شده:** {settings.referral_bonus_amount:,} تومان

📈 **جزئیات دعوت‌ها:**
✅ **کاربران خریدار:** {completed_users} نفر
⏳ **کاربران در انتظار:** {pending_users} نفر
📊 **کل دعوت‌ها:** {len(referred_users)} نفر

💡 **نکته:** کاربران در انتظار هنوز خریدی انجام نداده‌اند و پاداش شما پرداخت نشده است."""

        await event.edit(stats_message, buttons=[[Button.inline("🔙 بازگشت", data="referral_invite_friends")]])
