"""Helper utilities for admin referral system management."""

from __future__ import annotations

from telethon import Button
from telethon.tl.types import KeyboardInlineButtonRow, ReplyInlineMarkup

from app.db.crud.referral import ReferralManager
from app.db.crud.referral_payouts import PAYOUT_PENDING, ReferralPayoutCRUD
from app.db.crud.user import UserCRUD
from app.services.billing.referral import build_referral_start_param
from app.services.billing.referral_rewards import (
    REWARD_MODE_FIXED,
    REWARD_MODE_PERCENT,
    REWARD_PERCENT_MAX,
    REWARD_PERCENT_MIN,
    SIDE_BONUS,
    SIDE_REWARD,
    describe_referral_reward,
    describe_referral_side,
    referral_side_mode,
)
from app.telegram.keyboards.balance import balance_back_home_button
from app.telegram.keyboards.common import styled_copy_button
from app.telegram.state import set_step
from app.telegram.user.referral_earnings.service import earnings_enabled

NEWLINE = "\n"


SIDE_LABELS: dict[str, str] = {SIDE_REWARD: "پاداش دعوت کننده", SIDE_BONUS: "هدیه دعوت شده"}
SIDE_ICONS: dict[str, str] = {SIDE_REWARD: "💰", SIDE_BONUS: "🎁"}
MODE_TOGGLES: dict[str, str] = {
    "toggle_referral_reward_mode": SIDE_REWARD,
    "toggle_referral_bonus_mode": SIDE_BONUS,
}
PERCENT_STEPS: dict[str, str] = {
    "change_referral_percent": SIDE_REWARD,
    "change_referral_bonus_percent": SIDE_BONUS,
}
MAX_STEPS: dict[str, str] = {
    "change_referral_max": SIDE_REWARD,
    "change_referral_bonus_max": SIDE_BONUS,
}
FIXED_STEPS: dict[str, str] = {
    "change_referral_reward": SIDE_REWARD,
    "change_referral_bonus": SIDE_BONUS,
}
_BACK_ROW = [Button.inline("🔙 بازگشت", data="back_to_referral_management")]


def _step_for(steps: dict[str, str], side: str) -> str:
    return next(step for step, step_side in steps.items() if step_side == side)


def _side_lines(settings, side: str) -> list[str]:
    percent_mode = referral_side_mode(settings, side) == REWARD_MODE_PERCENT
    label = SIDE_LABELS[side]
    lines = [
        f"{SIDE_ICONS[side]} **{label}:** {describe_referral_side(settings, side)}",
        f"   ⚖️ نوع: {'درصدی از مبلغ اولین خرید' if percent_mode else 'مبلغ ثابت'}",
    ]
    if percent_mode:
        cap = int(getattr(settings, f"referral_{side}_max", 0) or 0)
        lines.append(f"   🔝 سقف: {f'{cap:,} تومان' if cap > 0 else 'بدون سقف'}")
    return lines


def referral_management_message(settings) -> str:
    status = "🟢 فعال" if settings.referral_enabled else "🔴 غیرفعال"
    lines = [
        "🎁 **مدیریت سیستم دعوت دوستان**",
        "",
        f"📊 **وضعیت سیستم:** {status}",
        "",
        *_side_lines(settings, SIDE_REWARD),
        "",
        *_side_lines(settings, SIDE_BONUS),
        "",
        *_earnings_lines(settings),
        "",
        "💡 پرداخت فقط یک بار و در **اولین خرید** کاربر دعوت‌شده انجام می‌شود. در حالت درصدی، "
        "مبنا مبلغی است که واقعاً از کیف پول کاربر کم شده (بعد از کد تخفیف). "
        "هر طرف را می‌توانید روی 0 بگذارید؛ طرفی که چیزی نگیرد پیامی هم دریافت نمی‌کند.",
        "",
        "برای تغییر تنظیمات از دکمه‌های زیر استفاده کنید:",
    ]
    return NEWLINE.join(lines)


def _side_buttons(settings, side: str) -> list:
    percent_mode = referral_side_mode(settings, side) == REWARD_MODE_PERCENT
    label = SIDE_LABELS[side]
    rows = [
        [
            Button.inline(
                f"⚖️ {label}: {'درصدی' if percent_mode else 'ثابت'} (تغییر)",
                data=_step_for(MODE_TOGGLES, side),
            )
        ]
    ]
    if percent_mode:
        rows.append(
            [
                Button.inline(f"📊 درصد {label}", data=_step_for(PERCENT_STEPS, side)),
                Button.inline(f"🔝 سقف {label}", data=_step_for(MAX_STEPS, side)),
            ]
        )
    else:
        rows.append([Button.inline(f"{SIDE_ICONS[side]} تغییر مبلغ {label}", data=_step_for(FIXED_STEPS, side))])
    return rows


def _earnings_lines(settings) -> list[str]:
    if not earnings_enabled(settings):
        return ["🏦 **مقصد پاداش دعوت کننده:** کیف پول (فوری قابل خرج)"]
    return [
        "🏦 **مقصد پاداش دعوت کننده:** درآمد دعوت (جدا از کیف پول)",
        f"   💸 برداشت به کارت: {'فعال' if settings.referral_withdraw_enabled else 'غیرفعال'}"
        f" — حداقل `{int(settings.referral_withdraw_min or 0):,}` تومان",
        f"   👛 انتقال به کیف پول: {'فعال' if settings.referral_transfer_enabled else 'غیرفعال'}",
    ]


def _earnings_buttons(settings) -> list:
    rows = [
        [
            Button.inline(
                f"🏦 مقصد پاداش: {'درآمد دعوت' if earnings_enabled(settings) else 'کیف پول'} (تغییر)",
                data="toggle_referral_destination",
            )
        ]
    ]
    if earnings_enabled(settings):
        rows += [
            [
                Button.inline(
                    f"💸 برداشت: {'✅' if settings.referral_withdraw_enabled else '❌'}",
                    data="toggle_referral_withdraw",
                ),
                Button.inline(
                    f"👛 انتقال به کیف پول: {'✅' if settings.referral_transfer_enabled else '❌'}",
                    data="toggle_referral_transfer",
                ),
            ],
            [Button.inline("📉 حداقل مبلغ برداشت", data="change_referral_withdraw_min")],
        ]
    rows.append([Button.inline("📋 درخواست‌های برداشت در انتظار", data="referral_pending_payouts")])
    return rows


def referral_management_buttons(settings) -> list:
    return [
        [
            Button.inline(
                f"🔄 {'غیرفعال کردن' if settings.referral_enabled else 'فعال کردن'} سیستم",
                data="toggle_referral_system",
            )
        ],
        *_side_buttons(settings, SIDE_REWARD),
        *_side_buttons(settings, SIDE_BONUS),
        *_earnings_buttons(settings),
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

    elif data in MODE_TOGGLES:
        side = MODE_TOGGLES[data]
        settings = await referral_manager.get_referral_settings()
        if not settings:
            await event.answer("❌ خطا در دریافت تنظیمات سیستم دعوت", alert=True)
            return
        percent_now = referral_side_mode(settings, side) == REWARD_MODE_PERCENT
        new_mode = REWARD_MODE_FIXED if percent_now else REWARD_MODE_PERCENT
        settings = await referral_manager.settings_crud.update_settings(**{f"referral_{side}_mode": new_mode})
        await event.edit(referral_management_message(settings), buttons=referral_management_buttons(settings))
        mode_text = "درصدی" if new_mode == REWARD_MODE_PERCENT else "ثابت"
        await event.answer(f"✅ نوع {SIDE_LABELS[side]} به «{mode_text}» تغییر کرد.")

    elif data in ("toggle_referral_destination", "toggle_referral_withdraw", "toggle_referral_transfer"):
        settings = await referral_manager.get_referral_settings()
        if not settings:
            await event.answer("❌ خطا در دریافت تنظیمات سیستم دعوت", alert=True)
            return
        if data == "toggle_referral_destination":
            update = {"referral_reward_destination": "wallet" if earnings_enabled(settings) else "earnings"}
        elif data == "toggle_referral_withdraw":
            update = {"referral_withdraw_enabled": not settings.referral_withdraw_enabled}
        else:
            update = {"referral_transfer_enabled": not settings.referral_transfer_enabled}
        settings = await referral_manager.settings_crud.update_settings(**update)
        await event.edit(referral_management_message(settings), buttons=referral_management_buttons(settings))
        await event.answer("✅ ذخیره شد.")

    elif data == "change_referral_withdraw_min":
        await event.edit(
            "📉 **حداقل مبلغ برداشت به کارت**"
            + NEWLINE * 2
            + "کمترین مبلغی که کاربر می‌تواند درخواست برداشت بدهد را به تومان بفرستید.",
            buttons=[_BACK_ROW],
        )
        await set_step(event.sender_id, data)

    elif data == "referral_pending_payouts":
        payouts, total = await ReferralPayoutCRUD().list_payouts(status=PAYOUT_PENDING, per_page=20)
        if not payouts:
            text = "📋 **درخواست‌های برداشت در انتظار**" + NEWLINE * 2 + "درخواستی در انتظار بررسی نیست ✅"
        else:
            text = (
                "📋 **درخواست‌های برداشت در انتظار**"
                + NEWLINE * 2
                + f"تعداد: {total}"
                + NEWLINE
                + "روی هر درخواست بزنید تا جزئیات و دکمه‌های پرداخت/رد را ببینید."
            )
        rows = [
            [Button.inline(f"💳 #{p.id} — {p.amount:,} تومان — {p.user_id}", data=f"refpay_view:{p.id}")]
            for p in payouts
        ]
        rows.append(_BACK_ROW)
        await event.edit(text, buttons=rows)

    elif data in PERCENT_STEPS:
        label = SIDE_LABELS[PERCENT_STEPS[data]]
        await event.edit(
            f"📊 **درصد {label}**"
            + NEWLINE * 2
            + f"یک عدد بین {REWARD_PERCENT_MIN} تا {REWARD_PERCENT_MAX} بفرستید."
            + NEWLINE
            + "مثلاً با `10`، برای خرید ۱۰۰ هزار تومانی، ۱۰ هزار تومان داده می‌شود."
            + NEWLINE
            + "برای «هیچ» نوع را روی ثابت بگذارید و مبلغ را 0 کنید.",
            buttons=[_BACK_ROW],
        )
        await set_step(event.sender_id, data)

    elif data in MAX_STEPS:
        label = SIDE_LABELS[MAX_STEPS[data]]
        await event.edit(
            f"🔝 **سقف {label} (حالت درصدی)**"
            + NEWLINE * 2
            + "بیشترین مبلغی که برای یک دعوت داده می‌شود را به تومان بفرستید."
            + NEWLINE
            + "برای «بدون سقف» عدد `0` را بفرستید.",
            buttons=[_BACK_ROW],
        )
        await set_step(event.sender_id, data)

    elif data in FIXED_STEPS:
        label = SIDE_LABELS[FIXED_STEPS[data]]
        await event.edit(
            f"{SIDE_ICONS[FIXED_STEPS[data]]} **تغییر مبلغ {label}**"
            + NEWLINE * 2
            + "مبلغ جدید را به تومان بفرستید. برای «هیچ» عدد `0` را بفرستید.",
            buttons=[_BACK_ROW],
        )
        await set_step(event.sender_id, data)

    elif data == "change_referral_banner":
        await event.edit(
            "🎨 **تغییر متن بنر**\n\nلطفاً متن جدید بنر را ارسال کنید.\n\n💡 **نکته:** می‌توانید از پلیس‌هولدر  های زیر استفاده کنید:\n• `{referral_link}` - لینک دعوت\n• `{referral_reward}` - پاداش دعوت کننده (مثلاً «۱۰٪ مبلغ اولین خرید» یا «40,000 تومان»)\n• `{referral_reward_amount}` - مبلغ ثابت پاداش دعوت کننده\n• `{referral_bonus}` - هدیه دعوت شده (مثلاً «۵٪ مبلغ اولین خرید» یا «20,000 تومان»)\n• `{referral_bonus_amount}` - مبلغ ثابت هدیه دعوت شده",
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
        referral_message = referral_message.replace("{referral_reward}", describe_referral_reward(settings))
        referral_message = referral_message.replace("{referral_bonus}", describe_referral_side(settings, SIDE_BONUS))
        referral_message = referral_message.replace("{referral_reward_amount}", f"{settings.referral_reward_amount:,}")
        referral_message = referral_message.replace("{referral_bonus_amount}", f"{settings.referral_bonus_amount:,}")

        copy_button = styled_copy_button("📋 کپی لینک دعوت", referral_link)

        stats_button = Button.inline("📊 آمار دعوت‌های من", data="my_referral_stats")
        back_home_button = await balance_back_home_button()

        rows = [KeyboardInlineButtonRow([copy_button]), KeyboardInlineButtonRow([stats_button])]
        # Shown while earnings are on, and afterwards to anyone who still has some to cash out.
        summary = await ReferralPayoutCRUD().earnings_summary(event.sender_id)
        if earnings_enabled(settings) or summary.available or summary.requested:
            rows.append(KeyboardInlineButtonRow([Button.inline("💼 درآمد دعوت و برداشت", data="refearn")]))
        rows.append(KeyboardInlineButtonRow([back_home_button]))
        custom_markup = ReplyInlineMarkup(rows)

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
🎁 **پاداش هر دعوت:** {describe_referral_reward(settings)}
💝 **هدیه دعوت شده:** {describe_referral_side(settings, SIDE_BONUS)}

📈 **جزئیات دعوت‌ها:**
✅ **کاربران خریدار:** {completed_users} نفر
⏳ **کاربران در انتظار:** {pending_users} نفر
📊 **کل دعوت‌ها:** {len(referred_users)} نفر

💡 **نکته:** کاربران در انتظار هنوز خریدی انجام نداده‌اند و پاداش شما پرداخت نشده است."""

        await event.edit(stats_message, buttons=[[Button.inline("🔙 بازگشت", data="referral_invite_friends")]])
