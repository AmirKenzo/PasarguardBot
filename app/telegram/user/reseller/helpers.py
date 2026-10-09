"""Reseller purchase flow shared helpers."""

from __future__ import annotations

import random
from datetime import UTC, datetime

import pytz
from telethon.tl import functions, types

from app import Kenzo
from app.db.crud.panels import PanelsManager
from app.db.crud.reseller_billing_snapshots import ResellerBillingSnapshotCRUD
from app.db.crud.reseller_plans import ResellerPlanManager
from app.db.crud.user import UserCRUD
from app.logger import get_logger
from app.services.billing.direct_pay_flow import (
    build_insufficient_balance_message,
    create_balance_button,
    is_direct_pay_enabled,
    start_direct_pay_topup,
)
from app.services.billing.direct_pay_store import KIND_RESELLER
from app.services.billing.reseller_pricing import (
    calculate_purchase_price,
    format_reseller_plan_button_short,
    validate_volume,
    volume_unit_label,
)
from app.services.panels.settings import panel_reseller_sale_enabled
from app.services.reseller.accounts import (
    ADMIN_LOCKED_STATUS,
    is_admin_locked,
    load_account_live_info,
    reveal_password,
)
from app.services.reseller.purchase import (
    ERR_DISCOUNT_UNAVAILABLE,
    ERR_INSUFFICIENT_BALANCE,
    ERR_INVALID_VOLUME,
    ERR_USERNAME_EXISTS,
    min_wallet_error,
    purchase_reseller_account,
)
from app.services.reseller.usage_cap import USAGE_CAPPED_STATUS
from app.services.telegram.rich_message import USAGE_HISTORY_PER_PAGE, prepare_rich_markdown
from app.telegram.keyboards.home import bhome_buttons
from app.telegram.shared.keyboards.panel_buttons import build_panel_display_button
from app.telegram.shared.reseller_plan_guides import (
    HOURLY,
    SETUP_FEE_LABEL,
    USAGE,
    format_active_minutes,
    max_users_label,
    mode_name,
    plan_price_line,
    renew_preview_lines,
    setup_fee,
    toman,
)
from app.telegram.state import clear_user, get_data, set_data, set_step
from app.telegram.user.reseller.states import RESELLER_FLOW_MSG_KEY
from app.utils.formatting.dates import timestamp_to_persian_expiry
from app.utils.formatting.traffic import format_size
from app.utils.text.bot_texts import get_bot_text

logger = get_logger(__name__)


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
    if plan.data_limit:
        label = "حجم پلن" if plan.pricing_mode == "fixed" else "سقف کل ترافیک"
        data_line = f"**📊 {label}:** {format_size(plan.data_limit)}\n"
    elif not volume:
        data_line = "**📊 حجم:** نامحدود\n"
    duration_line = f"**⏰ مدت:** {plan.duration} روز\n" if plan.duration else "**⏰ مدت:** بدون انقضا\n"
    if plan.pricing_mode in (USAGE, HOURLY):
        fee = setup_fee(plan)
        fee_line = (
            f"**💳 {SETUP_FEE_LABEL}:** {amount:,} تومان (یک‌بار، الان کسر می‌شود)\n"
            if fee
            else "**💳 پرداخت اولیه:** ندارد\n"
        )
        amount_line = f"{fee_line}**💰 هزینه:** {plan_price_line(plan)} (کسر دقیقه‌ای از کیف پول)\n"
    else:
        amount_line = f"**💰 مبلغ:** {amount:,} تومان\n"
    return (
        f"**✅ تأیید خرید نمایندگی**\n\n"
        f"**📋 نوع پلن:** {mode_name(plan.pricing_mode)}\n"
        f"{volume_line}{data_line}{duration_line}"
        f"**👤 یوزر:** `{username}`\n"
        f"**👥 سقف یوزر:** {plan.max_users or 'نامحدود'}\n"
        f"{discount_line}"
        f"{amount_line}"
    )


def build_reseller_renew_confirm_text(
    account,
    plan,
    *,
    amount: int,
    discount_code: str | None = None,
    current_limit: int = 0,
    used_traffic: int = 0,
    now: int = 0,
    balance: int | None = None,
) -> str:
    """Renewal review: before → after of volume, expiry and users, then the price."""
    lines = [
        f"**💎 تمدید نمایندگی `{account.username}`**",
        "",
        f"**📋 پلن:** {mode_name(plan.pricing_mode)} (همان پلن خریداری‌شده)",
        "",
        "**🔄 قبل ← بعد از تمدید:**",
        *renew_preview_lines(account, plan, current_limit=current_limit, used_traffic=used_traffic, now=now),
        "",
        "ℹ️ تمدید چیزی را ریست نمی‌کند: روز و حجم باقی‌مانده و یوزرهای اضافه حفظ می‌شوند.",
        "",
    ]
    if discount_code:
        lines.append(f"**🎟 کد تخفیف:** `{discount_code}`")
        lines.append(f"**💸 قبل از تخفیف:** {toman(calculate_purchase_price(plan))}")
    lines.append(f"**💰 مبلغ تمدید:** {toman(amount)}")
    if balance is not None:
        lines.append(f"**👛 موجودی فعلی:** {toman(balance)}")
        if balance < amount:
            lines.append(f"⚠️ برای تمدید {toman(amount - balance)} موجودی کم دارید.")
    return "\n".join(lines)


def format_plan_button_text(plan) -> str:
    if plan.display_button_text:
        return plan.display_button_text.split("\n", 1)[0].strip()
    return format_reseller_plan_button_short(plan)


_ALERT_ERRORS = {ERR_INVALID_VOLUME, ERR_USERNAME_EXISTS, ERR_DISCOUNT_UNAVAILABLE, ERR_INSUFFICIENT_BALANCE}


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

    outcome = await purchase_reseller_account(
        user_id,
        plan_id=plan_id,
        panel_code=panel_code,
        username=username,
        volume=float(volume_raw) if volume_raw else None,
        amount=amount,
        discount_code=discount_code,
    )
    if not outcome.ok:
        if event is not None and outcome.error in _ALERT_ERRORS:
            await event.answer(outcome.message, alert=True)
        elif event is not None:
            await event.edit(outcome.message, buttons=await bhome_buttons(user_id, lang))
        elif outcome.error == ERR_INVALID_VOLUME:
            await Kenzo.send_message(user_id, outcome.message)
        else:
            await Kenzo.send_message(user_id, outcome.message, buttons=await bhome_buttons(user_id, lang))
        return False, outcome.error

    plan = outcome.plan
    volume = outcome.volume
    volume_text = ""
    if volume:
        volume_text = f"**📦 حجم:** {volume:g} {volume_unit_label(plan.pricing_mode)}\n"
    duration_text = f"**⏰ مدت:** {plan.duration} روز\n" if plan.duration else ""
    users_text = f"**👥 سقف یوزر:** {plan.max_users or 'نامحدود'}\n"
    traffic_text = f"**📊 سقف ترافیک:** {format_size(outcome.data_limit)}\n" if outcome.data_limit else ""
    if plan.pricing_mode not in (USAGE, HOURLY) or int(amount) > 0:
        paid_text = f"💵 مبلغ `{int(amount):,}` تومان از موجودی کسر شد.\n"
    else:
        paid_text = "💳 پرداخت اولیه نداشت؛ هزینه به‌صورت دقیقه‌ای از کیف پول کسر می‌شود.\n"

    success_text = (
        f"**🎉 نمایندگی پنل با موفقیت فعال شد!**\n\n"
        f"**#️⃣ کد نمایندگی:** `{outcome.account_code}`\n"
        f"**🌐 آدرس پنل:** `{outcome.panel_url}`\n"
        f"**👤 نام کاربری:** `{username}`\n"
        f"**🔑 رمز عبور:** `{outcome.password}`\n\n"
        f"{volume_text}{duration_text}{users_text}{traffic_text}\n"
        f"{paid_text}"
        f"💰 موجودی جدید: `{outcome.new_balance:,}` تومان\n\n"
        f"⚠️ رمز را در جای امن ذخیره کنید."
    )

    if event is not None:
        await event.delete()
    await clear_user(user_id)
    await set_step(user_id, "home")

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

    wallet_error = await min_wallet_error(plan, user_id)
    if wallet_error:
        await event.delete()
        await event.respond(wallet_error, buttons=await create_balance_button(user_id))
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
            if await is_direct_pay_enabled() and await start_direct_pay_topup(event):
                return
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
    info = await load_account_live_info(account)
    used = info.used_traffic
    live_limit = info.data_limit
    total_users = info.total_users
    live_rate = info.live_rate

    mode_label = mode_name(account.pricing_mode)
    status_fa = await reseller_status_label(account, account.telegram_id)

    lines = [
        f"**🏢 نمایندگی `{account.username}`**",
        f"**#️⃣ کد:** `{account.code}`",
        f"**📛 پنل:** {info.panel_name}",
        f"**🌐 آدرس ورود:** `{info.login_url}`",
        f"**👤 یوزر ادمین:** `{account.username}`",
    ]

    if show_password:
        lines.append(f"**🔑 رمز:** `{reveal_password(account)}`")

    lines.extend(
        [
            "",
            f"**📋 نوع پلن:** {mode_label}" + (f" · پلن #{info.plan.id}" if info.plan else ""),
            f"**📊 وضعیت ربات:** {status_fa}",
            f"**📡 وضعیت پنل:** `{info.admin_status}`",
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

    lines.append(f"**👥 سقف یوزر:** {max_users_label(account.max_users, account.extra_users)}")
    lines.append(f"**👤 یوزرهای ساخته‌شده:** {total_users}")

    if account.expiration_time:
        lines.append(f"**⏰ انقضا:** {timestamp_to_persian_expiry(account.expiration_time)}")
        if info.grace_days_left is not None:
            lines.append(f"**🗑 حذف خودکار:** تا {info.grace_days_left} روز دیگر")

    if account.pricing_mode in ("hourly", "usage"):
        balance = info.balance or 0
        billed_total = info.billed_total or 0
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
        delta_bytes = snap.used_traffic if snap.used_traffic < prev_used else snap.used_traffic - prev_used
    return int(delta_bytes or 0)


def snapshot_usage_text(snapshots: list, index: int) -> str:
    """What one billing row charged for: active time for hourly rows, traffic for usage rows."""
    snap = snapshots[index]
    minutes = getattr(snap, "billed_minutes", None)
    if minutes is not None:
        return format_active_minutes(minutes)
    return format_size(_snapshot_delta_bytes(snapshots, index), decimal_places=2)


def usage_history_header(account) -> tuple[str, str]:
    """(page title, usage column) of the charge report; hourly plans are charged for time, not traffic."""
    if account.pricing_mode == HOURLY:
        return f"# 🧾 گزارش کسر `{account.username}`", "زمان فعال"
    return f"# 📊 گزارش مصرف `{account.username}`", "مصرف"


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

    title, usage_column = usage_history_header(account)
    lines = [
        title,
        "",
        f"**💸 مجموع شارژ:** `{total_billed:,}` تومان",
        f"**🧾 Records:** `{count}`",
        "",
        "---",
        "",
        "<details>",
        "<summary>📋 Usage History</summary>",
        "",
        f"| تاریخ | {usage_column} | مبلغ |",
        "|------|------|------|",
    ]

    if not snapshots:
        lines.append("| — | — | — |")
    else:
        for index, snap in enumerate(snapshots):
            usage = snapshot_usage_text(snapshots, index)
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
