"""Shared helpers for user service management flow."""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime
from urllib.parse import unquote

from pasarguard import PasarguardAPI, UserResponse
from telethon import Button
from telethon.errors.rpcerrorlist import MessageNotModifiedError
from telethon.tl import functions, types

from app import Kenzo
from app.db.crud.keyboards import get_button_text
from app.db.crud.panels import PanelsManager
from app.db.crud.plans import PlanManager
from app.db.crud.services import ServiceCRUD
from app.db.crud.user import UserCRUD
from app.logger import get_logger
from app.services.billing.renewal import (
    require_panel_userid,
)
from app.services.panels.config_links import fetch_user_config_links
from app.services.subscriptions.links import (
    build_tunnel_subscription_url,
    resolve_subscription_display_urls,
)
from app.telegram.keyboards.buy import (
    buy_empty_list_button,
    ms_renew_back_button,
    ms_sub_links_back_button,
    ms_sub_links_get_all_button,
    ms_sub_links_next_button,
    ms_sub_links_prev_button,
)
from app.telegram.shared.utils.usage_chart import (
    build_day_detail_buttons,
    build_day_detail_message,
    build_usage_chart_buttons,
    build_usage_chart_message,
    fetch_daily_usage,
    fetch_day_node_usage,
)
from app.telegram.state import get_data, get_step
from app.telegram.user.services.states import SUB_LINKS_PAGE_LIMIT
from app.utils.formatting.dates import Time_Date, relative_time, timestamp_to_persian_expiry
from app.utils.formatting.traffic import format_ip_limit, format_size, format_usage_progress_bar
from app.utils.text.bot_texts import get_bot_text
from config import ADMIN_ID, BOT_TAG

logger = get_logger(__name__)


async def build_service_text(service, panel_name: str, user) -> str:
    identifier = service.username if user.show_config_name else service.code
    if user.show_service_word:
        identifier = f"سرویس {identifier}"
    parts = [str(identifier)]
    if user.show_volume:
        if hasattr(service, "data_limit_reset_strategy") and service.data_limit_reset_strategy != "no_reset":
            reset_text_map = {
                "day": "روزانه",
                "week": "هفتگی",
                "month": "ماهانه",
                "year": "سالانه",
            }
            period_text = reset_text_map.get(getattr(service, "data_limit_reset_strategy", None), "نامحدود")
            per_limit_text = format_size(service.package_size, decimal_places=0)
            parts.append(f"{period_text} {per_limit_text}")
        else:
            parts.append(format_size(service.package_size, decimal_places=1))
    if user.show_panel:
        parts.append(panel_name)
    return " - ".join(parts)


async def display_user_services(user_id, current_page, edit_message=False, original_event=None):
    services = await ServiceCRUD().get_services_reverse(user_id)

    user = await UserCRUD().read_user(user_id)
    row_size = user.service_buttons_per_row or 1
    row_count = user.service_button_rows or 5
    panel_limit = min(row_size * row_count, 20)

    if not services:
        no_services_text = await get_bot_text(key="no_services_message", default="شما هیچ سرویسی ندارید.", lang="fa")
        buy_button = [await buy_empty_list_button()]
        await Kenzo.send_message(entity=user_id, message=no_services_text, buttons=buy_button)
        return

    total_services = len(services)
    num_pages = (total_services + panel_limit - 1) // panel_limit
    start_index = (current_page - 1) * panel_limit
    end_index = start_index + panel_limit
    current_services = services[start_index:end_index]

    panels_by_code = {panel.code: panel for panel in await PanelsManager().get_all_panels()}

    service_buttons = []
    current_row = []
    for service in current_services:
        panel = panels_by_code.get(service.in_panel)
        panel_display_name = panel.name if panel is not None else "پنل نامشخص"
        text = await build_service_text(service, panel_display_name, user)
        current_row.append(Button.inline(text, data=f"service_info:{service.code}"))

        if len(current_row) == row_size:
            service_buttons.append(current_row)
            current_row = []
    if current_row:
        service_buttons.append(current_row)

    navigation_buttons = []
    if current_page > 1:
        navigation_buttons.append(Button.inline("صفحه قبلی ->", data=f"PrevService:{current_page}"))
    if current_page < num_pages:
        navigation_buttons.append(Button.inline("<- صفحه بعدی", data=f"NextService:{current_page}"))

    my_services_intro = await get_bot_text(key="my_services_intro", default="🔑 لیست سرویس‌های شما:", lang="fa")
    message_text = f"{my_services_intro}\n**💡 تعداد اشتراک‌های شما :** {total_services}\n."
    buttons = [*service_buttons, navigation_buttons]

    if edit_message and original_event:
        await Kenzo.edit_message(
            entity=original_event.original_update.user_id,
            message=original_event.original_update.msg_id,
            text=message_text,
            buttons=buttons,
        )
    else:
        await Kenzo.send_message(entity=user_id, message=message_text, buttons=buttons)


async def _deny_unless_service_owner_or_admin(event, serv_msg) -> bool:
    """Return True when access is denied (alert already sent)."""
    if int(serv_msg.id or 0) != int(event.sender_id) and event.sender_id not in ADMIN_ID:
        await event.answer("❌ این کانفیگ برای شما نیست!", alert=True)
        return True
    return False


async def _back_to_service(sender_id: int, service_code: str) -> str:
    """Return service_info_admin:code if viewer is admin, else service_info:code."""
    step = (await get_step(sender_id)) or ""
    if step.startswith("ToServiceAdmin:"):
        return f"service_info_admin:{service_code}"
    from_admin = await get_data(sender_id, "from_admin")
    if from_admin:
        return f"service_info_admin:{service_code}"
    return f"service_info:{service_code}"


async def edit_service_view(event, text, buttons=None, *, qr_url=None, subscription_link=None, service_code=None):
    """Edit service info in-place."""
    del subscription_link, service_code
    if qr_url:
        await edit_message_with_qr(event, text, qr_url, buttons=buttons)
        return
    await event.edit(text, buttons=buttons)


async def edit_message_with_qr(event, text, qr_url, buttons=None, invert_media=True):
    """Edit a message with QR code displayed above the text"""
    message, entities = Kenzo.parse_mode.parse(text)
    msg = await event.get_message()
    await Kenzo(
        functions.messages.EditMessageRequest(
            peer=msg.peer_id,
            id=msg.id,
            message=message,
            media=types.InputMediaWebPage(qr_url, force_large_media=False, force_small_media=True, optional=True),
            invert_media=invert_media,
            entities=entities,
            reply_markup=Kenzo.build_reply_markup(buttons) if buttons else None,
        )
    )


async def build_service_info_message_text(serv_msg, info_panel, user: UserResponse) -> tuple[str, str]:
    """English docstring for build_service_info_message_text."""
    subscription_url = user.subscription_url
    subscription_url = (
        subscription_url if subscription_url.startswith("http") else f"{info_panel.base_url}{subscription_url}"
    )
    tunnel_subscription_url = build_tunnel_subscription_url(subscription_url, info_panel.tunnel_url)
    display_subscription_url, tunnel_url_text, primary_subscription_url = resolve_subscription_display_urls(
        info_panel, subscription_url, tunnel_subscription_url
    )
    total_remain = user.data_limit - user.used_traffic
    status_texts = {
        "active": "✅ فعال",
        "expired": "🕔 منقضی شده (تاریخ اکانت تمام شده)",
        "limited": "🪫 محدود (حجم تمام شده)",
        "disabled": "❌ غیرفعال",
        "on-hold": "🔋 در انتظار (زمان کانفیگ بعد از اتصال شروع میشود)",
    }
    service_volume_text = format_size(user.data_limit, decimal_places=0)
    reset_info_line = ""
    plan_type = None
    if serv_msg.package_size:
        try:
            current_plan = await PlanManager().get_plan_by_volume_for_display(
                gb=serv_msg.package_size / (1024**3), panel_code=serv_msg.in_panel
            )
            if current_plan and hasattr(current_plan, "plan_type"):
                plan_type = current_plan.plan_type
        except Exception:
            pass
    if plan_type == "unlimited_volume":
        service_volume_text = f"{format_size(user.data_limit, decimal_places=0)} (مصرف منصفانه)"
    if hasattr(serv_msg, "data_limit_reset_strategy") and serv_msg.data_limit_reset_strategy != "no_reset":
        reset_strategy_fa = {"day": "روزانه", "week": "هفتگی", "month": "ماهانه", "year": "سالانه"}.get(
            serv_msg.data_limit_reset_strategy, "دوره‌ای"
        )
        now = datetime.now()
        if user.expire.tzinfo is not None:
            now = datetime.now(UTC)
        remaining_days = (user.expire - now).days
        if remaining_days < 0:
            remaining_days = 0
        daily_limit_bytes = user.data_limit
        if serv_msg.data_limit_reset_strategy == "day":
            total_possible_bytes = daily_limit_bytes * remaining_days
            period_text = "روزانه"
        elif serv_msg.data_limit_reset_strategy == "week":
            total_possible_bytes = daily_limit_bytes * (remaining_days // 7)
            period_text = "هفتگی"
        elif serv_msg.data_limit_reset_strategy == "month":
            total_possible_bytes = daily_limit_bytes * (remaining_days // 30)
            period_text = "ماهانه"
        elif serv_msg.data_limit_reset_strategy == "year":
            total_possible_bytes = daily_limit_bytes * (remaining_days // 365)
            period_text = "سالانه"
        else:
            total_possible_bytes = daily_limit_bytes
            period_text = "دوره‌ای"
        if plan_type != "unlimited_volume":
            service_volume_text = f"{format_size(user.data_limit, decimal_places=1)} ({period_text})"
        remaining_volume_text = format_size(user.data_limit - user.used_traffic, decimal_places=2)
        reset_info_line = f"🔄 **نحوه ریست:** حجم شما هر {reset_strategy_fa} ریست می‌شود\n"
        reset_info_line += (
            f"📊 **کل حجم قابل مصرف تا پایان اشتراک:** {format_size(total_possible_bytes, decimal_places=1)}\n"
        )
    else:
        remaining_volume_text = format_size(total_remain, decimal_places=2)

    ip_limit_text = format_ip_limit(getattr(serv_msg, "ip_limit", 0))
    status_value = status_texts.get(user.status.lower(), "نامشخص")
    expiry_date_value = timestamp_to_persian_expiry(user.expire.timestamp())
    last_connection_value = relative_time(user.online_at) if user.online_at else ""
    edit_at_value = relative_time(user.edit_at) if user.edit_at else ""
    lifetime_used_traffic_value = format_size(int(getattr(user, "lifetime_used_traffic", 0) or 0), decimal_places=2)

    service_info_template = await get_bot_text(
        key="service_info_message",
        default=(
            "🎛 **وضعیت سرویس:** {status}\n\n"
            "**🔐 محدودیت کاربر و دستگاه :** {ip_limit}\n"
            "**🌍 پلان :** {plan_name}\n"
            "#⃣ **کد سرویس(در ربات):** `{service_code}`\n"
            "**🔷 اسم کانفیگ:** `{config_name}`\n"
            "**📥حجم مصرفی:** {used_volume}\n"
            "**📊 حجم کل مصرفی:** {lifetime_used_traffic}\n"
            "{usage_progress}\n"
            "**🎲 حجم باقی مانده:** {remaining_volume}\n"
            "**🗳 حجم سرویس :** {total_volume}\n"
            "{reset_info}"
            "**📅 فعال تا تاریخ :** {expiry_date}\n"
            "{last_connection}"
            "{edit_at}"
            "**🚀 لینک آیپی‌ثابت سابسکریپشن جهت دسترسی یکجا به تمامی لوکیشن‌ها**\n\n"
            "{BOT_TAG} (Subscription) :\n"
            "`{subscription_url}`"
            "{tunnel_subscription_url}"
            "\n▫️ یکی از گزینه های زیر را انتخاب کنید.\n\n"
            "❌ جهت قطع دسترسی دیگران تغییر ساب بزنید.\n\n"
            "🚥 برای دیدن آموزش ها از منوی ربات روی دکمه (🚦راهنما یا /help) بزنید."
        ),
        lang="fa",
    )

    service_info_text = service_info_template.replace("{status}", status_value)
    service_info_text = service_info_text.replace("{ip_limit}", ip_limit_text)
    service_info_text = service_info_text.replace("{plan_name}", info_panel.name)
    service_info_text = service_info_text.replace("{service_code}", str(serv_msg.code))
    service_info_text = service_info_text.replace("{config_name}", serv_msg.username)
    service_info_text = service_info_text.replace("{used_volume}", format_size(user.used_traffic, decimal_places=2))
    service_info_text = service_info_text.replace("{lifetime_used_traffic}", lifetime_used_traffic_value)
    service_info_text = service_info_text.replace(
        "{usage_progress}", format_usage_progress_bar(user.used_traffic, user.data_limit)
    )
    service_info_text = service_info_text.replace("{remaining_volume}", remaining_volume_text)
    service_info_text = service_info_text.replace("{total_volume}", service_volume_text)
    service_info_text = service_info_text.replace("{reset_info}", reset_info_line)
    service_info_text = service_info_text.replace("{expiry_date}", expiry_date_value)
    service_info_text = service_info_text.replace(
        "{last_connection}",
        f"**🔋 آخرین اتصال: ** `{last_connection_value}`\n" if last_connection_value else "",
    )
    service_info_text = service_info_text.replace(
        "{edit_at}",
        f"**📝 آخرین ویرایش کانفیگ:** `{edit_at_value}`\n" if edit_at_value else "",
    )
    service_info_text = service_info_text.replace("{BOT_TAG}", BOT_TAG)
    service_info_text = service_info_text.replace("{subscription_url}", display_subscription_url)
    service_info_text = service_info_text.replace("{tunnel_subscription_url}", tunnel_url_text)
    return service_info_text, primary_subscription_url


def group_durations(durations):
    """English docstring for group_durations."""
    individual_durations = {}

    for duration in durations:
        individual_durations[f"{duration} روزه"] = [duration]

    return individual_durations


async def generate_volume_buttons_tamdid(config_code, duration_group=None, sender_id: int | None = None):
    """English docstring for generate_volume_buttons_tamdid."""
    from app.telegram.shared.keyboards.plan_buttons import build_plan_inline_button

    try:
        _sts, result = await ServiceCRUD().get_service(config_code)
        if duration_group:
            plans = await PlanManager().get_all_plans(panel_code=result.in_panel)
            plans = [p for p in plans if p.duration in duration_group]
        else:
            plans = await PlanManager().get_all_plans(panel_code=result.in_panel)

        if not plans:
            return [[Button.inline("❌ هیچ پلنی برای این پنل یافت نشد", data="no_plans")]]

        current_plan_type = None
        if result.package_size:
            current_plan = await PlanManager().get_plan_by_volume_for_display(
                gb=result.package_size / (1024**3), panel_code=result.in_panel
            )
            if current_plan and hasattr(current_plan, "plan_type"):
                current_plan_type = current_plan.plan_type

        if current_plan_type:
            filtered_plans = [
                plan for plan in plans if hasattr(plan, "plan_type") and plan.plan_type == current_plan_type
            ]
        else:
            filtered_plans = plans

        if not filtered_plans:
            return [[Button.inline("❌ هیچ پلن هم‌نوع برای تمدید یافت نشد", data="no_compatible_plans")]]

        panel_manager = PanelsManager()
        panel = await panel_manager.get_panel_by_code(result.in_panel)

        sorted_plans = sorted(filtered_plans, key=lambda plan: plan.storage)
        volume_buttons = []
        for plan in sorted_plans:
            volume_buttons.append(
                [await build_plan_inline_button(plan, panel, f"SelectPlanTamdid_{plan.id}", context="tamdid")]
            )
        back_data = await _back_to_service(sender_id, str(config_code)) if sender_id else f"service_info:{config_code}"
        volume_buttons.append([await ms_renew_back_button(back_data)])
        return volume_buttons
    except Exception as e:
        logger.error(f"خطا در دریافت داده‌ها: {e}")
        return [[Button.inline("خطا در دریافت پنل‌ها", data="error")]]


async def check_user_balance(user_id, required_amount):
    user = await UserCRUD().read_user(user_id=user_id)

    if user is None:
        return False, "کاربر یافت نشد."  # If user doesn't exist

    balance = user.amount  # Assume user balance is stored in the balance field

    required = int(required_amount)

    if balance < 0:
        return False, "موجودی شما منفی است. لطفاً موجودی خود را بررسی کنید."  # Negative balance
    if balance == 0 or balance < required:
        # Message to redirect to balance increase section
        message = f"‼️ موجودی کیف پول شما کافی نیست\n\n💰 برای خرید این پلان شما باید ({required:,} تومان) موجودی داشته باشید.\n\n📌 برای افزایش موجودی، روی دکمه 'افزایش موجودی' کلیک کنید و پس از افزایش با یکی از روش‌های پرداخت، مجدد مراحل خرید را طی کنید."
        return False, message
    return True, "موجودی کافی است."  # Sufficient balance


async def create_balance_button(user_id):
    """English docstring for create_balance_button."""
    balance_button_text = await get_button_text("bt.menu_add_balance", "💰 افزایش موجودی")
    return [[Button.inline(balance_button_text, data="back_to_balance")]]


async def display_subscription_links(
    event,
    service_code: str,
    current_page: int = 1,
    selected_index: int | None = None,
    *,
    back_data: str | None = None,
):
    try:
        service, serv_msg = await ServiceCRUD().get_service(code=service_code)
        if not service:
            await event.answer("❌ سرویس یافت نشد!", alert=True)
            return
        if await _deny_unless_service_owner_or_admin(event, serv_msg):
            return

        info_panel = await PanelsManager().get_panel_by_code(code=serv_msg.in_panel)
        if not info_panel:
            await event.answer("❌ پنل یافت نشد!", alert=True)
            return

        links = await fetch_user_config_links(info_panel, require_panel_userid(serv_msg))

        if not links:
            await event.edit("❌ هیچ لینکی برای این سرویس پیدا نشد.")
            return

        total_links = len(links)
        num_pages = (total_links + SUB_LINKS_PAGE_LIMIT - 1) // SUB_LINKS_PAGE_LIMIT
        if current_page < 1:
            current_page = 1
        if current_page > num_pages:
            current_page = num_pages
        start_index = (current_page - 1) * SUB_LINKS_PAGE_LIMIT
        end_index = start_index + SUB_LINKS_PAGE_LIMIT

        current_links = links[start_index:end_index]
        link_buttons: list[list[Button]] = []
        row: list[Button] = []
        for idx, link in enumerate(current_links):
            raw_name = link.rsplit("#", 1)[-1] if "#" in link else f"Config {start_index + idx + 1}"
            name = unquote(raw_name)
            row.append(Button.inline(name, data=f"showSubLink:{service_code}:{start_index + idx}"))
            if len(row) == 2:
                link_buttons.append(row)
                row = []
        if row:
            link_buttons.append(row)

        navigation = []
        if current_page > 1:
            navigation.append(await ms_sub_links_prev_button(service_code, current_page))
        if current_page < num_pages:
            navigation.append(await ms_sub_links_next_button(service_code, current_page))

        if navigation:
            link_buttons.append(navigation)
        if not getattr(event, "via_inline", False):
            link_buttons.append([await ms_sub_links_get_all_button(service_code)])
        _back_links = back_data or await _back_to_service(event.sender_id, service_code)
        link_buttons.append([await ms_sub_links_back_button(_back_links)])

        message = ""
        if selected_index is not None and 0 <= selected_index < len(links):
            selected_link = links[selected_index]
            raw_name = selected_link.rsplit("#", 1)[-1] if "#" in selected_link else f"Config {selected_index + 1}"
            name = unquote(raw_name)
            message += f"**{name}**\n`{selected_link}`\n\n"
        message += "لطفا یکی از کانفیگ‌ها را انتخاب کنید:"

        await event.edit(message, buttons=link_buttons)
    except Exception as e:
        await event.edit("❌ خطایی رخ داد هنگام دریافت لینک‌ها")
        logger.error(f"❌ خطایی رخ داد هنگام دریافت لینک‌ها:\n{e!s}")


async def display_subscription_clients(event, service_code: str, *, back_data: str | None = None) -> None:
    back = back_data or await _back_to_service(event.sender_id, service_code)
    buttons = [[Button.inline("بازگشت", data=back)]]

    try:
        service, serv_msg = await ServiceCRUD().get_service(code=service_code)
        if not service:
            await event.answer("❌ سرویس یافت نشد!", alert=True)
            return

        info_panel = await PanelsManager().get_panel_by_code(code=serv_msg.in_panel)
        if not info_panel:
            await event.answer("❌ پنل یافت نشد!", alert=True)
            return

        result = await PasarguardAPI(info_panel.base_url).get_user_sub_update_list_by_username(
            username=serv_msg.username, token=info_panel.cookie
        )
        if not result.updates:
            await event.edit("هیچ کلاینتی برای این سرویس یافت نشد.", buttons=buttons)
            return

        rows = []
        for item in result.updates:
            ts = (
                getattr(item, "created_at", None)
                or getattr(item, "updated_at", None)
                or getattr(item, "last_seen", None)
                or getattr(item, "last_seen_at", None)
                or getattr(item, "timestamp", None)
            )
            rows.append((Time_Date(ts).get("stamp", 0) if ts else 0, ts, item))
        rows.sort(key=lambda r: r[0], reverse=True)
        visible = rows[:10]
        now = datetime.now(tz=UTC)

        def en_ago(ts) -> str:
            if not ts:
                return "unknown"
            if isinstance(ts, (int, float)):
                dt = datetime.fromtimestamp(ts, tz=UTC)
            elif isinstance(ts, datetime):
                dt = ts.replace(tzinfo=UTC) if ts.tzinfo is None else ts.astimezone(UTC)
            elif isinstance(ts, str):
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                dt = dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)
            else:
                return "unknown"
            sec = max(0, int((now - dt).total_seconds()))
            if sec < 60:
                return "just now"
            if sec < 3600:
                return f"{sec // 60}m ago"
            if sec < 86400:
                return f"{sec // 3600}h ago"
            if sec < 2592000:
                return f"{sec // 86400}d ago"
            if sec < 31536000:
                return f"{sec // 2592000}mo ago"
            return f"{sec // 31536000}y ago"

        lines = [
            "# 🧾 آپدیت‌های لینک ساب",
            f"**🔷 کانفیگ:** `{serv_msg.username}`",
            "",
            f"**#️⃣ کد سرویس:** `{serv_msg.code}`",
            "",
            f"**👥 تعداد آپدیت‌ها:** `{len(rows)}`",
            "",
            f"**📌 نمایش:** `{len(visible)} آپدیت آخر`",
            "",
            f"**🟢 آخرین آپدیت ساب:** `{en_ago(rows[0][1])}`",
            "",
            f"**🕰 اولین رکورد:** `{en_ago(rows[-1][1])}`",
            "",
            "---",
            "",
            "<details>",
            "<summary>📊 نمایش لیست کلاینت‌ها</summary>",
            "",
            "| Client | Updated |",
            "|--------|---------|",
        ]
        for _, ts, item in visible:
            client = getattr(item, "user_agent", None) or getattr(item, "ua", None) or "نامشخص"
            lines.append(f"| {client} | {en_ago(ts)} |")
        lines.extend(["", "</details>"])
        if len(rows) > len(visible):
            lines.extend(["", f"> … و **{len(rows) - len(visible)} آپدیت قدیمی‌تر** نمایش داده نشد."])

        msg = await event.get_message()
        await Kenzo(
            functions.messages.EditMessageRequest(
                peer=msg.peer_id,
                id=msg.id,
                message="",
                rich_message=types.InputRichMessageMarkdown("\n".join(lines), rtl=True),
                reply_markup=Kenzo.build_reply_markup(buttons),
            )
        )
    except Exception as e:
        await event.edit("❌ خطایی رخ داد هنگام دریافت اطلاعات کلاینت‌ها", buttons=buttons)
        logger.error(f"❌ خطایی رخ داد هنگام دریافت کلاینت‌ها:\n{e}")


async def display_usage_chart(
    event,
    service_code: str,
    *,
    days: int = 7,
    page: int = 0,
    back_data: str | None = None,
    service_owner_id: int | None = None,
) -> None:
    try:
        service, serv_msg = await ServiceCRUD().get_service(code=service_code)
        if not service:
            await event.answer("❌ سرویس یافت نشد!", alert=True)
            return
        owner_id = service_owner_id if service_owner_id is not None else event.sender_id
        if service_owner_id is not None:
            if serv_msg.id != service_owner_id:
                await event.answer("❌ این کانفیگ برای شما نیست!", alert=True)
                return
        elif serv_msg.id != owner_id and event.sender_id not in ADMIN_ID:
            await event.answer("❌ این کانفیگ برای شما نیست!", alert=True)
            return

        info_panel = await PanelsManager().get_panel_by_code(code=serv_msg.in_panel)
        if not info_panel:
            await event.answer("❌ پنل یافت نشد!", alert=True)
            return

        _back = back_data or await _back_to_service(event.sender_id, service_code)
        await event.answer("⏳ در حال دریافت نمودار مصرف...")
        daily_points = await fetch_daily_usage(
            info_panel,
            require_panel_userid(serv_msg),
            days=days,
        )
        message = build_usage_chart_message(
            username=serv_msg.username,
            service_code=service_code,
            daily_points=daily_points,
            days=days,
            page=page,
        )
        buttons = build_usage_chart_buttons(
            service_code,
            days=days,
            page=page,
            daily_points=daily_points,
            back_data=_back,
        )
        with contextlib.suppress(MessageNotModifiedError):
            await event.edit(message, buttons=buttons, parse_mode="md")
    except MessageNotModifiedError:
        pass
    except Exception as e:
        _back_ex = back_data or await _back_to_service(event.sender_id, service_code)
        await event.edit(
            "❌ خطایی رخ داد هنگام دریافت نمودار مصرف",
            buttons=[[Button.inline("بازگشت", data=_back_ex)]],
        )
        logger.error(f"❌ خطا در نمودار مصرف:\n{e!s}")


async def display_usage_chart_day(
    event,
    service_code: str,
    day_iso: str,
    *,
    days: int = 7,
    page: int = 0,
    back_data: str | None = None,
    service_owner_id: int | None = None,
) -> None:
    try:
        service, serv_msg = await ServiceCRUD().get_service(code=service_code)
        if not service:
            await event.answer("❌ سرویس یافت نشد!", alert=True)
            return
        owner_id = service_owner_id if service_owner_id is not None else event.sender_id
        if service_owner_id is not None:
            if serv_msg.id != service_owner_id:
                await event.answer("❌ این کانفیگ برای شما نیست!", alert=True)
                return
        elif serv_msg.id != owner_id and event.sender_id not in ADMIN_ID:
            await event.answer("❌ این کانفیگ برای شما نیست!", alert=True)
            return

        info_panel = await PanelsManager().get_panel_by_code(code=serv_msg.in_panel)
        if not info_panel:
            await event.answer("❌ پنل یافت نشد!", alert=True)
            return

        day = datetime.fromisoformat(day_iso).date()
        _back = back_data or await _back_to_service(event.sender_id, service_code)
        await event.answer("⏳ در حال دریافت جزئیات...")
        node_points = await fetch_day_node_usage(
            info_panel,
            require_panel_userid(serv_msg),
            day,
        )
        message = build_day_detail_message(
            username=serv_msg.username,
            service_code=service_code,
            day=day,
            node_points=node_points,
        )
        buttons = build_day_detail_buttons(
            service_code,
            days=days,
            page=page,
            back_data=_back,
        )
        with contextlib.suppress(MessageNotModifiedError):
            await event.edit(message, buttons=buttons, parse_mode="md")
    except MessageNotModifiedError:
        pass
    except Exception as e:
        _back_ex = back_data or await _back_to_service(event.sender_id, service_code)
        await event.edit(
            "❌ خطایی رخ داد هنگام دریافت جزئیات مصرف",
            buttons=[[Button.inline("بازگشت", data=_back_ex)]],
        )
        logger.error(f"❌ خطا در جزئیات مصرف:\n{e!s}")


SERVICE_CALLBACK_PREFIXES = (
    "TamdidVPN_",
    "SelectDurationGroupForTamdid:",
    "SelectPlanTamdid_",
    "confirm_purchase_tamdid_",
    "ApplyCodeTakhfifTamdid",
    "othersSubLinks:",
    "NextSubLinks:",
    "PrevSubLinks:",
    "showSubLink:",
    "get_single_links:",
    "get_xhttp_links:",
    "showClients:",
    "UsageChart:",
    "UsageChartDay:",
    "service_info:",
    "DeleteService:",
    "ConfirmDelete:",
    "ChangeLink:",
    "ChangeSub:",
    "KharidSize:",
    "upgSize@",
    "KharidZaman:",
    "upgTime@",
    "getQrcode:",
    "TransferConfig:",
)
