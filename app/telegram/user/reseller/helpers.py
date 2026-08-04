"""Reseller purchase flow shared helpers."""

from __future__ import annotations

import json
import random
import time
from datetime import UTC, datetime

import pytz
from httpx import HTTPStatusError
from pasarguard import AdminCreate
from telethon.tl import functions, types

from app import Kenzo
from app.db.crud.discount_codes import DiscountCodeManager
from app.db.crud.panels import PanelsManager
from app.db.crud.reseller_accounts import ResellerAccountCRUD
from app.db.crud.reseller_billing_snapshots import ResellerBillingSnapshotCRUD
from app.db.crud.reseller_plans import ResellerPlanManager
from app.db.crud.settings import SettingsManager
from app.db.crud.user import UserCRUD, update_Money
from app.logger import get_logger
from app.services.billing.direct_pay_flow import (
    build_insufficient_balance_message,
    create_balance_button,
)
from app.services.billing.direct_pay_store import KIND_RESELLER
from app.services.billing.reseller_pricing import (
    calculate_purchase_price,
    format_reseller_plan_button_short,
    pricing_mode_label,
    requires_wallet_for_purchase,
    resolve_live_unit_price,
    validate_volume,
    volume_unit_label,
)
from app.services.panels.admins import (
    activate_reseller_admin,
    admin_username_exists,
    build_admin_create_payload,
    compute_reseller_data_limit,
    compute_reseller_expiration,
    create_reseller_admin,
    generate_admin_password,
    get_reseller_admin,
    purge_reseller_admin,
    suspend_reseller_admin,
)
from app.services.panels.settings import get_panel_login_url, panel_reseller_sale_enabled
from app.services.reseller.logging import send_reseller_log
from app.services.reseller.usage_cap import USAGE_CAPPED_STATUS
from app.services.telegram.rich_message import USAGE_HISTORY_PER_PAGE, prepare_rich_markdown
from app.telegram.keyboards.home import bhome_buttons
from app.telegram.shared.keyboards.panel_buttons import build_panel_display_button
from app.telegram.state import clear_user, get_data, set_data, set_step
from app.telegram.user.reseller.states import RESELLER_FLOW_MSG_KEY
from app.utils.formatting.dates import Time_Date, timestamp_to_persian_expiry
from app.utils.formatting.traffic import format_size
from app.utils.security.crypto import decrypt_data, encrypt_data
from app.utils.text.bot_texts import get_bot_text

logger = get_logger(__name__)

ADMIN_LOCKED_STATUS = "admin_paused"


def is_admin_locked(account) -> bool:
    return account.status == ADMIN_LOCKED_STATUS


async def get_reseller_text(key: str, default: str, user_id: int | None = None, **replacements: str) -> str:
    lang = await _user_lang(user_id) if user_id else "fa"
    text = await get_bot_text(key=key, default=default, lang=lang)
    for placeholder, value in replacements.items():
        text = text.replace(f"{{{placeholder}}}", str(value))
    return text


async def reseller_status_label(account, user_id: int | None = None) -> str:
    labels = {
        "active": "🟢 فعال",
        "suspended": "⛔️ تعلیق (کمبود موجودی)",
        "paused": "⏸ غیرفعال (توسط شما)",
        ADMIN_LOCKED_STATUS: "⛔️ غیرفعال (توسط ادمین)",
        USAGE_CAPPED_STATUS: "⛔️ غیرفعال (سقف مصرف)",
        "expired": "⌛ منقضی",
    }
    return labels.get(account.status, account.status)


async def _user_lang(user_id: int) -> str:
    info = await UserCRUD().read_user(user_id)
    return info.language if info and info.language else "fa"


async def check_user_balance(user_id: int, required_amount: int):
    user = await UserCRUD().read_user(user_id=user_id)
    if user is None:
        return False, "کاربر یافت نشد."
    balance = user.amount
    required = int(required_amount)
    if balance < required:
        return False, ""
    return True, "موجودی کافی است."


async def show_reseller_panel_picker(event) -> None:
    from telethon import events

    user_id = event.sender_id
    panel_codes = await ResellerPlanManager().get_panels_with_plans(enabled_only=True)
    if not panel_codes:
        if isinstance(event, events.CallbackQuery.Event):
            await event.answer("پلن نمایندگی فعالی وجود ندارد.", alert=True)
        else:
            await event.respond("پلن نمایندگی فعالی وجود ندارد.")
        return
    buttons = await build_reseller_panel_list_buttons(panel_codes)
    text = await get_reseller_text(
        "reseller_buy_panel_picker",
        "**🏢 خرید نمایندگی**\n\nپنل مورد نظر را انتخاب کنید:",
        user_id,
    )
    await reseller_flow_edit(event, text, buttons=buttons)
    await set_step(user_id, "reseller_select_panel")


async def build_reseller_panel_list_buttons(panel_codes: list) -> list:
    from app.telegram.keyboards import reseller as rs_buttons

    buttons = []
    for code in panel_codes:
        panel = await PanelsManager().get_panel_by_code(code=code)
        if panel and panel_reseller_sale_enabled(panel):
            buttons.append([await build_panel_display_button(panel, f"ResellerPanel_{code}")])
    buttons.append([await rs_buttons.rs_buy_cancel_button()])
    return buttons


async def reseller_flow_edit(event, text: str, *, buttons=None):
    """Edit the active reseller purchase/renew bot message (works for callbacks and text replies)."""
    from telethon import events

    user_id = event.sender_id
    if isinstance(event, events.CallbackQuery.Event):
        msg = await event.edit(text, buttons=buttons)
        await set_data(user_id, RESELLER_FLOW_MSG_KEY, str(msg.id))
        return msg

    msg_id = await get_data(user_id, RESELLER_FLOW_MSG_KEY)
    if msg_id:
        try:
            msg = await event.client.edit_message(event.chat_id, int(msg_id), text, buttons=buttons)
            await set_data(user_id, RESELLER_FLOW_MSG_KEY, str(msg.id))
            return msg
        except Exception:
            pass
    msg = await event.respond(text, buttons=buttons)
    await set_data(user_id, RESELLER_FLOW_MSG_KEY, str(msg.id))
    return msg


def apply_discount_amount(amount: int, discount_percentage: float) -> int:
    return max(0, int(amount - (amount * float(discount_percentage) / 100)))


async def resolve_reseller_purchase_amount(user_id: int, plan, volume: float | None) -> tuple[int, str | None]:
    base = calculate_purchase_price(plan, volume)
    discounted_raw = await get_data(user_id, "reseller_discount_amount")
    code = await get_data(user_id, "reseller_discount_code")
    if discounted_raw is not None and code:
        try:
            return int(discounted_raw), code
        except TypeError, ValueError:
            pass
    return base, None


def build_reseller_confirm_text(
    plan, *, username: str, volume: float | None, amount: int, discount_code: str | None = None
) -> str:
    volume_line = ""
    if volume:
        volume_line = f"**📦 حجم:** {volume:g} {volume_unit_label(plan.pricing_mode)}\n"
    discount_line = ""
    if discount_code:
        original = calculate_purchase_price(plan, volume)
        discount_line = f"**🎟 کد تخفیف:** `{discount_code}`\n**💸 قبل از تخفیف:** {original:,} تومان\n"
    data_line = ""
    if plan.pricing_mode == "fixed" and plan.data_limit:
        data_line = f"**📊 حجم پلن:** {format_size(plan.data_limit)}\n"
    duration_line = f"**⏰ مدت:** {plan.duration} روز\n" if plan.duration else ""
    return (
        f"**✅ تأیید خرید نمایندگی**\n\n"
        f"**پلن:** {pricing_mode_label(plan.pricing_mode)}\n"
        f"{volume_line}{data_line}{duration_line}"
        f"**👤 یوزر:** `{username}`\n"
        f"**👥 سقف یوزر:** {plan.max_users or 'نامحدود'}\n"
        f"{discount_line}"
        f"**💰 مبلغ:** {amount:,} تومان\n"
    )


def build_reseller_renew_confirm_text(plan, *, amount: int, discount_code: str | None = None) -> str:
    discount_line = ""
    if discount_code:
        original = calculate_purchase_price(plan)
        discount_line = f"**🎟 کد تخفیف:** `{discount_code}`\n**💸 قبل از تخفیف:** {original:,} تومان\n"
    data_line = f"**📊 حجم اضافه:** {format_size(plan.data_limit)}\n" if plan.data_limit else ""
    duration_line = f"**⏰ تمدید:** {plan.duration} روز\n" if plan.duration else ""
    return (
        f"**💎 تأیید تمدید نمایندگی**\n\n"
        f"**پلن:** {pricing_mode_label(plan.pricing_mode)}\n"
        f"{data_line}{duration_line}"
        f"{discount_line}"
        f"**💰 مبلغ:** {amount:,} تومان\n"
    )


def format_plan_button_text(plan) -> str:
    if plan.display_button_text:
        return plan.display_button_text.split("\n", 1)[0].strip()
    return format_reseller_plan_button_short(plan)


async def build_initial_billing_state(plan, amount: int) -> dict:
    now = Time_Date()["stamp"]
    return {"started_at": now, "last_billed_at": now, "setup_fee": amount, "total_billed": 0}


async def create_reseller_purchase_for_user(
    user_id: int,
    *,
    amount: int,
    payload: dict | None = None,
    discount_code: str | None = None,
    event=None,
) -> tuple[bool, str]:
    lang = await _user_lang(user_id)

    if payload:
        plan_id = payload.get("reseller_plan_id")
        panel_code = payload.get("reseller_panel_code")
        username = payload.get("reseller_username")
        volume_raw = payload.get("reseller_volume")
        discount_code = discount_code or payload.get("discount_code")
    else:
        plan_id = await get_data(user_id, "reseller_plan_id")
        panel_code = await get_data(user_id, "reseller_panel_code")
        username = await get_data(user_id, "reseller_username")
        volume_raw = await get_data(user_id, "reseller_volume")

    plan = await ResellerPlanManager().get_plan(plan_id)
    if not plan or not panel_code or not username:
        msg = "خطا: اطلاعات خرید ناقص است."
        if event is not None:
            await event.edit(msg, buttons=await bhome_buttons(user_id, lang))
        else:
            await Kenzo.send_message(user_id, msg, buttons=await bhome_buttons(user_id, lang))
        return False, "missing_context"

    volume = float(volume_raw) if volume_raw else None
    if volume is not None:
        ok, err = validate_volume(plan, volume)
        if not ok:
            if event is not None:
                await event.answer(err, alert=True)
            else:
                await Kenzo.send_message(user_id, err)
            return False, "invalid_volume"

    panel = await PanelsManager().get_panel_by_code(code=int(panel_code))
    if not panel:
        msg = "پنل یافت نشد."
        if event is not None:
            await event.edit(msg, buttons=await bhome_buttons(user_id, lang))
        else:
            await Kenzo.send_message(user_id, msg, buttons=await bhome_buttons(user_id, lang))
        return False, "panel_not_found"

    if await admin_username_exists(panel, username):
        msg = "این نام کاربری ادمین در پنل وجود دارد."
        if event is not None:
            await event.answer(msg, alert=True)
        else:
            await Kenzo.send_message(user_id, msg, buttons=await bhome_buttons(user_id, lang))
        return False, "username_exists"

    password = generate_admin_password(username=username)
    data_limit = compute_reseller_data_limit(plan, volume)
    admin_payload: AdminCreate = build_admin_create_payload(
        plan,
        username=username,
        password=password,
        telegram_id=user_id,
        data_limit=data_limit,
        max_users=plan.max_users,
    )

    start_time = time.time()
    try:
        created = await create_reseller_admin(panel, admin_payload)
    except HTTPStatusError as e:
        logger.error("create_reseller_admin failed: %s", e.response.text)
        msg = "خطا در ساخت ادمین پنل. لطفاً با پشتیبانی تماس بگیرید."
        if event is not None:
            await event.edit(msg, buttons=await bhome_buttons(user_id, lang))
        else:
            await Kenzo.send_message(user_id, msg, buttons=await bhome_buttons(user_id, lang))
        return False, "panel_create_failed"

    account_code = await ResellerAccountCRUD().generate_unique_code()
    expiration = compute_reseller_expiration(plan)
    billing_state = await build_initial_billing_state(plan, amount)

    new_amount = await update_Money(user_id=user_id, Money=-int(amount))
    await ResellerAccountCRUD().create_account(
        code=account_code,
        telegram_id=user_id,
        panel_code=int(panel_code),
        panel_admin_id=getattr(created, "id", None),
        username=username,
        password_encrypted=encrypt_data(password),
        plan_id=plan.id,
        pricing_mode=plan.pricing_mode,
        data_limit=data_limit or None,
        max_users=plan.max_users or None,
        purchased_volume=volume,
        createtime=Time_Date()["stamp"],
        expiration_time=expiration,
        status="active",
        billing_state=json.dumps(billing_state, ensure_ascii=False),
    )

    if discount_code:
        await DiscountCodeManager().update_discount_usage(code=discount_code)

    panel_url = get_panel_login_url(panel)
    volume_text = ""
    if volume:
        volume_text = f"**📦 حجم:** {volume:g} {volume_unit_label(plan.pricing_mode)}\n"
    duration_text = f"**⏰ مدت:** {plan.duration} روز\n" if plan.duration else ""
    users_text = f"**👥 سقف یوزر:** {plan.max_users or 'نامحدود'}\n"
    traffic_text = f"**📊 سقف ترافیک:** {format_size(data_limit)}\n" if data_limit else ""

    success_text = (
        f"**🎉 نمایندگی پنل با موفقیت فعال شد!**\n\n"
        f"**#️⃣ کد نمایندگی:** `{account_code}`\n"
        f"**🌐 آدرس پنل:** `{panel_url}`\n"
        f"**👤 نام کاربری:** `{username}`\n"
        f"**🔑 رمز عبور:** `{password}`\n\n"
        f"{volume_text}{duration_text}{users_text}{traffic_text}\n"
        f"💵 مبلغ `{int(amount):,}` تومان از موجودی کسر شد.\n"
        f"💰 موجودی جدید: `{new_amount:,}` تومان\n\n"
        f"⚠️ رمز را در جای امن ذخیره کنید."
    )

    if event is not None:
        await event.delete()
    await clear_user(user_id)
    await set_step(user_id, "home")

    ok, account = await ResellerAccountCRUD().get_account(account_code)
    extra = [
        f"💸 <b>مبلغ:</b> <code>{int(amount):,}</code> تومان",
        f"⏱ <b>زمان ساخت:</b> <code>{time.time() - start_time:.2f}</code> ثانیه",
    ]
    if discount_code:
        extra.append(f"🎟 <b>کد تخفیف:</b> <code>{discount_code}</code>")
    await send_reseller_log(
        "📢 خرید نمایندگی جدید",
        account=account if ok else None,
        actor_id=user_id,
        extra_lines=extra
        if ok
        else [
            f"👤 <b>کاربر:</b> <code>{user_id}</code>",
            f"🎫 <b>کد:</b> <code>{account_code}</code>",
            f"🏢 <b>یوزر ادمین:</b> <code>{username}</code>",
            f"📛 <b>پنل:</b> <code>{panel_code}</code>",
            *extra,
        ],
    )
    if event is not None:
        await event.respond("✅", buttons=await bhome_buttons(user_id, lang))
        await event.respond(success_text)
    else:
        await Kenzo.send_message(user_id, "✅", buttons=await bhome_buttons(user_id, lang))
        await Kenzo.send_message(user_id, success_text)
    return True, ""


async def _complete_reseller_purchase(event, *, amount: int, discount_code: str | None = None) -> None:
    user_id = event.sender_id
    lang = await _user_lang(user_id)

    plan_id = await get_data(user_id, "reseller_plan_id")
    panel_code = await get_data(user_id, "reseller_panel_code")
    username = await get_data(user_id, "reseller_username")
    volume_raw = await get_data(user_id, "reseller_volume")

    plan = await ResellerPlanManager().get_plan(plan_id)
    if not plan or not panel_code or not username:
        await event.edit("خطا: اطلاعات خرید ناقص است.", buttons=await bhome_buttons(user_id, lang))
        return

    volume = float(volume_raw) if volume_raw else None
    if volume is not None:
        ok, err = validate_volume(plan, volume)
        if not ok:
            await event.answer(err, alert=True)
            return

    settings = await SettingsManager().get_settings()
    if requires_wallet_for_purchase(plan) and settings:
        user = await UserCRUD().read_user(user_id)
        min_balance = int(settings.reseller_min_wallet_balance or 0)
        if user and user.amount < min_balance:
            await event.delete()
            await event.respond(
                f"برای نمایندگی {pricing_mode_label(plan.pricing_mode)} حداقل موجودی {min_balance:,} تومان لازم است.",
                buttons=await create_balance_button(user_id),
            )
            return

    is_sufficient, message = await check_user_balance(user_id, amount)
    if not is_sufficient:
        volume_label = ""
        if volume:
            volume_label = f"{volume:g} {volume_unit_label(plan.pricing_mode)}"
        if not message:
            message = await build_insufficient_balance_message(
                user_id,
                amount,
                kind=KIND_RESELLER,
                product_label=getattr(plan, "name", None) or "پنل نمایندگی",
                volume=volume_label,
            )
        await event.delete()
        await event.respond(message, buttons=await create_balance_button(user_id))
        return

    await create_reseller_purchase_for_user(
        user_id,
        amount=amount,
        discount_code=discount_code,
        event=event,
    )


def generate_reseller_username(prefix: str = "res") -> str:
    return f"{prefix}{random.randint(1000, 999999)}"


async def build_reseller_account_detail_text(account, *, show_password: bool = False) -> str:
    panel = await PanelsManager().get_panel_by_code(code=account.panel_code)
    panel_name = panel.name if panel else str(account.panel_code)
    login_url = get_panel_login_url(panel) if panel else "—"
    plan = await ResellerPlanManager().get_plan(account.plan_id) if account.plan_id else None

    admin = await get_reseller_admin(panel, account.username) if panel else None
    used = int(getattr(admin, "used_traffic", 0) or 0) if admin else 0
    live_limit = (
        int(getattr(admin, "data_limit", 0) or account.data_limit or 0) if admin else int(account.data_limit or 0)
    )
    total_users = int(getattr(admin, "total_users", 0) or 0) if admin else 0
    admin_status = getattr(admin, "status", None) or account.status

    mode_label = pricing_mode_label(account.pricing_mode)
    status_fa = await reseller_status_label(account, account.telegram_id)

    live_rate = resolve_live_unit_price(account, plan)

    lines = [
        f"**🏢 نمایندگی `{account.username}`**",
        f"**#️⃣ کد:** `{account.code}`",
        f"**📛 پنل:** {panel_name}",
        f"**🌐 آدرس ورود:** `{login_url}`",
        f"**👤 یوزر ادمین:** `{account.username}`",
    ]

    if show_password:
        password = decrypt_data(account.password_encrypted)
        lines.append(f"**🔑 رمز:** `{password}`")

    lines.extend(
        [
            "",
            f"**📋 نوع پلن:** {mode_label}",
            f"**📊 وضعیت ربات:** {status_fa}",
            f"**📡 وضعیت پنل:** `{admin_status}`",
        ]
    )

    if account.pricing_mode in ("per_gb", "per_tb") and account.purchased_volume:
        unit = volume_unit_label(account.pricing_mode)
        lines.append(f"**📦 حجم خریداری‌شده:** {account.purchased_volume:g} {unit}")
    if live_rate and account.pricing_mode == "hourly":
        lines.append(f"**💰 نرخ ساعتی:** {int(live_rate):,} تومان/ساعت")
        lines.append(f"**⏱ نرخ دقیقه‌ای:** ~{max(1, int(live_rate // 60)):,} تومان/دقیقه")
    elif live_rate and account.pricing_mode == "usage":
        lines.append(f"**💰 نرخ مصرف:** {int(live_rate):,} تومان/گیگ (از پلن فعلی)")
    elif live_rate and account.pricing_mode in ("per_gb", "per_tb"):
        lines.append(f"**💰 قیمت واحد:** {int(live_rate):,} تومان")

    if live_limit:
        pct = min(100, int(used * 100 / live_limit)) if live_limit else 0
        lines.append(f"**📥 مصرف:** {format_size(used)} از {format_size(live_limit)} ({pct}%)")
    else:
        lines.append(f"**📥 مصرف:** {format_size(used)} (سقف نامحدود)")

    if account.pricing_mode == "usage":
        cap = account.usage_cap_bytes
        if cap:
            cap_pct = min(100, int(used * 100 / cap)) if cap else 0
            lines.append(f"**🚦 سقف مصرف دستی:** {format_size(used)} / {format_size(cap)} ({cap_pct}%)")
        else:
            lines.append("**🚦 سقف مصرف دستی:** بدون محدودیت")

    if account.max_users:
        lines.append(f"**👥 سقف یوزر:** {total_users} / {account.max_users}")
    else:
        lines.append(f"**👥 یوزرهای ساخته‌شده:** {total_users}")

    if account.expiration_time:
        lines.append(f"**⏰ انقضا:** {timestamp_to_persian_expiry(account.expiration_time)}")
        if account.status == "expired":
            grace_left = max(0, account.expiration_time + 7 * 86400 - Time_Date()["stamp"])
            days_left = max(1, grace_left // 86400) if grace_left else 0
            lines.append(f"**🗑 حذف خودکار:** تا {days_left} روز دیگر")

    if account.pricing_mode in ("hourly", "usage"):
        state = ResellerAccountCRUD.load_billing_state(account.billing_state)
        user = await UserCRUD().read_user(account.telegram_id)
        balance = user.amount if user else 0
        total_billed = int(state.get("total_billed") or 0)
        _, snapshot_total = await ResellerBillingSnapshotCRUD().get_usage_totals(account.code)
        billed_total = max(total_billed, snapshot_total)
        lines.append(f"**💳 موجودی کیف پول:** {balance:,} تومان")
        if account.pricing_mode == "usage":
            lines.append(f"**💸 مجموع کسر مصرفی:** {billed_total:,} تومان")
        if account.pricing_mode == "hourly":
            rate = int(live_rate or 0)
            lines.append(f"**⚠️ حداقل برای ادامه:** ~{max(1, rate // 60):,} تومان/دقیقه")
        if account.status == "paused":
            lines.append("**ℹ️ پنل غیرفعال است — تا زمان فعال‌سازی، موجودی کسر نمی‌شود.**")
        if account.status == USAGE_CAPPED_STATUS:
            lines.append("**⛔️ مصرف به سقف دستی رسیده است. برای فعال‌سازی مجدد، سقف را افزایش دهید یا حذف کنید.**")
        if is_admin_locked(account):
            lines.append(
                "**⛔️ این نمایندگی توسط ادمین غیرفعال شده است. تا زمان فعال‌سازی مجدد توسط پشتیبانی، امکان مدیریت آن وجود ندارد.**"
            )

    return "\n".join(lines)


async def show_account_credentials(event, account) -> None:
    from app.telegram.user.reseller.keyboards import build_my_reseller_account_buttons

    if is_admin_locked(account):
        await event.answer(
            "این نمایندگی توسط ادمین غیرفعال شده و امکان مشاهده رمز وجود ندارد.",
            alert=True,
        )
        return

    text = await build_reseller_account_detail_text(account, show_password=True)
    buttons = await build_my_reseller_account_buttons(account)
    await event.edit(text, buttons=buttons)


async def show_account_detail(event, account) -> None:
    from app.telegram.user.reseller.keyboards import build_my_reseller_account_buttons

    text = await build_reseller_account_detail_text(account, show_password=False)
    buttons = await build_my_reseller_account_buttons(account)
    await event.edit(text, buttons=buttons)


async def pause_reseller_account(account) -> tuple[bool, str]:
    if is_admin_locked(account):
        return False, "این نمایندگی توسط ادمین غیرفعال شده است."
    if account.status == "paused":
        return True, "پنل از قبل غیرفعال است."
    if account.status == "expired":
        return False, "نمایندگی منقضی شده است."
    if account.status == USAGE_CAPPED_STATUS:
        return False, "پنل به‌خاطر سقف مصرف غیرفعال است. ابتدا سقف را تغییر دهید."

    panel = await PanelsManager().get_panel_by_code(code=account.panel_code)
    if not panel:
        return False, "پنل یافت نشد."

    try:
        await suspend_reseller_admin(panel, account.username)
    except Exception as exc:
        logger.error("pause reseller failed code=%s: %s", account.code, exc)
        return False, "خطا در غیرفعال‌سازی پنل."

    await ResellerAccountCRUD().update_account(account.code, status="paused")
    await send_reseller_log(
        "⏸ غیرفعال‌سازی نمایندگی توسط کاربر",
        account=account,
        actor_id=account.telegram_id,
    )
    return True, "پنل غیرفعال شد. تا زمان فعال‌سازی مجدد، موجودی کسر نمی‌شود."


async def pause_reseller_account_by_admin(account, *, actor_id: int | None = None) -> tuple[bool, str]:
    if is_admin_locked(account):
        return True, "پنل از قبل توسط ادمین غیرفعال است."
    if account.status == "expired":
        return False, "نمایندگی منقضی شده است."

    panel = await PanelsManager().get_panel_by_code(code=account.panel_code)
    if not panel:
        return False, "پنل یافت نشد."

    try:
        await suspend_reseller_admin(panel, account.username)
    except Exception as exc:
        logger.error("admin pause reseller failed code=%s: %s", account.code, exc)
        return False, "خطا در غیرفعال‌سازی پنل."

    await ResellerAccountCRUD().update_account(account.code, status=ADMIN_LOCKED_STATUS)
    await send_reseller_log(
        "⛔️ غیرفعال‌سازی نمایندگی توسط ادمین",
        account=account,
        actor_id=actor_id,
        actor_role="ادمین",
    )
    return True, "نمایندگی توسط ادمین غیرفعال شد."


async def resume_reseller_account(account) -> tuple[bool, str]:
    if is_admin_locked(account):
        return False, "فعال‌سازی این نمایندگی فقط توسط ادمین امکان‌پذیر است."
    if account.status != "paused":
        return False, "این نمایندگی در حالت غیرفعال نیست."

    panel = await PanelsManager().get_panel_by_code(code=account.panel_code)
    if not panel:
        return False, "پنل یافت نشد."

    if account.pricing_mode in ("hourly", "usage"):
        user = await UserCRUD().read_user(account.telegram_id)
        plan = await ResellerPlanManager().get_plan(account.plan_id) if account.plan_id else None
        if account.pricing_mode == "usage" and user and user.amount < 1:
            return False, "برای فعال‌سازی مجدد موجودی کیف پول کافی نیست."
        if account.pricing_mode == "hourly":
            rate = int(resolve_live_unit_price(account, plan))
            if user and user.amount < max(1, rate // 60):
                return False, "موجودی برای ادامه پلن ساعتی کافی نیست."

    try:
        await activate_reseller_admin(panel, account.username)
    except Exception as exc:
        logger.error("resume reseller failed code=%s: %s", account.code, exc)
        return False, "خطا در فعال‌سازی پنل."

    await ResellerAccountCRUD().update_account(account.code, status="active")
    await send_reseller_log(
        "▶️ فعال‌سازی نمایندگی توسط کاربر",
        account=account,
        actor_id=account.telegram_id,
    )
    return True, "پنل دوباره فعال شد."


async def resume_reseller_account_by_admin(account, *, actor_id: int | None = None) -> tuple[bool, str]:
    if account.status not in ("paused", ADMIN_LOCKED_STATUS):
        return False, "این نمایندگی در حالت غیرفعال نیست."

    panel = await PanelsManager().get_panel_by_code(code=account.panel_code)
    if not panel:
        return False, "پنل یافت نشد."

    if account.status == "paused" and account.pricing_mode in ("hourly", "usage"):
        user = await UserCRUD().read_user(account.telegram_id)
        plan = await ResellerPlanManager().get_plan(account.plan_id) if account.plan_id else None
        if account.pricing_mode == "usage" and user and user.amount < 1:
            return False, "موجودی کیف پول کاربر برای فعال‌سازی کافی نیست."
        if account.pricing_mode == "hourly":
            rate = int(resolve_live_unit_price(account, plan))
            if user and user.amount < max(1, rate // 60):
                return False, "موجودی کاربر برای ادامه پلن ساعتی کافی نیست."

    try:
        await activate_reseller_admin(panel, account.username)
    except Exception as exc:
        logger.error("admin resume reseller failed code=%s: %s", account.code, exc)
        return False, "خطا در فعال‌سازی پنل."

    await ResellerAccountCRUD().update_account(account.code, status="active")
    await send_reseller_log(
        "▶️ فعال‌سازی نمایندگی توسط ادمین",
        account=account,
        actor_id=actor_id,
        actor_role="ادمین",
    )
    return True, "نمایندگی توسط ادمین فعال شد."


async def delete_reseller_account(
    account,
    *,
    actor_id: int | None = None,
    actor_role: str = "کاربر",
) -> tuple[bool, str]:
    panel = await PanelsManager().get_panel_by_code(code=account.panel_code)
    deleted_users = 0
    admin_removed = False
    if panel:
        deleted_users, admin_removed = await purge_reseller_admin(panel, account)

    await ResellerBillingSnapshotCRUD().delete_snapshots_for_account(account.code)
    await ResellerAccountCRUD().delete_account(account.code)
    await send_reseller_log(
        "🗑 حذف نمایندگی",
        account=account,
        actor_id=actor_id or account.telegram_id,
        actor_role=actor_role,
        extra_lines=[
            f"👥 <b>یوزر حذف‌شده:</b> <code>{deleted_users}</code>",
            f"🧹 <b>ادمین از پنل:</b> <code>{'بله' if admin_removed else 'خیر'}</code>",
        ],
    )
    if not admin_removed and panel:
        return False, "حذف ادمین از پنل ناموفق بود. با پشتیبانی تماس بگیرید."
    return True, f"نمایندگی `{account.username}` و {deleted_users} یوزر وابسته حذف شدند."


async def build_usage_history_text(
    account, page: int = 0, per_page: int = USAGE_HISTORY_PER_PAGE
) -> tuple[str, bool, bool]:
    markdown, has_prev, has_next = await _build_usage_history_rich_markdown(account, page=page, per_page=per_page)
    return markdown, has_prev, has_next


def _format_billing_datetime(ts: int) -> str:
    iran_tz = pytz.timezone("Asia/Tehran")
    dt = datetime.fromtimestamp(int(ts), tz=UTC).astimezone(iran_tz)
    return dt.strftime("%Y-%m-%d %H:%M")


def _snapshot_delta_bytes(snapshots: list, index: int) -> int:
    snap = snapshots[index]
    prev_used = snapshots[index + 1].used_traffic if index + 1 < len(snapshots) else None
    if prev_used is None:
        delta_bytes = snap.used_traffic if snap.billed_amount > 0 else 0
    else:
        delta_bytes = max(0, snap.used_traffic - prev_used)
    return int(delta_bytes or 0)


def _format_charged_toman(amount: int) -> str:
    if amount <= 0:
        return "0 تومان"
    return f"{amount:,} تومان"


async def _build_usage_history_rich_markdown(
    account, page: int = 0, per_page: int = USAGE_HISTORY_PER_PAGE
) -> tuple[str, bool, bool]:
    offset = page * per_page
    snapshots = await ResellerBillingSnapshotCRUD().get_snapshots(account.code, limit=per_page + 1, offset=offset)
    has_next = len(snapshots) > per_page
    snapshots = snapshots[:per_page]
    count, total_billed = await ResellerBillingSnapshotCRUD().get_usage_totals(account.code)

    lines = [
        f"# 📊 گزارش مصرف `{account.username}`",
        "",
        f"**💸 مجموع شارژ:** `{total_billed:,}` تومان",
        f"**🧾 Records:** `{count}`",
        "",
        "---",
        "",
        "<details>",
        "<summary>📋 Usage History</summary>",
        "",
        "| تاریخ | مصرف | مبلغ |",
        "|------|------|------|",
    ]

    if not snapshots:
        lines.append("| — | — | — |")
    else:
        for index, snap in enumerate(snapshots):
            delta_bytes = _snapshot_delta_bytes(snapshots, index)
            usage = format_size(delta_bytes, decimal_places=2)
            charged = _format_charged_toman(snap.billed_amount)
            lines.append(f"| {_format_billing_datetime(snap.snapshot_at)} | {usage} | {charged} |")

    lines.extend(["", "</details>"])
    if page > 0 or has_next:
        lines.extend(["", f"> Page `{page + 1}`"])

    return "\n".join(lines), page > 0, has_next


async def show_usage_history(event, account, page: int = 0) -> None:
    from app.telegram.user.reseller.keyboards import build_usage_history_buttons

    markdown, has_prev, has_next = await _build_usage_history_rich_markdown(account, page=page)
    buttons = await build_usage_history_buttons(account.code, page, has_prev, has_next)
    prepared = prepare_rich_markdown(markdown)

    try:
        msg = await event.get_message()
        await Kenzo(
            functions.messages.EditMessageRequest(
                peer=msg.peer_id,
                id=msg.id,
                message="",
                rich_message=types.InputRichMessageMarkdown(prepared, rtl=True),
                reply_markup=Kenzo.build_reply_markup(buttons),
            )
        )
    except Exception as exc:
        logger.error("reseller usage rich message failed code=%s: %s", account.code, exc)
        await event.edit(prepared, buttons=buttons)
