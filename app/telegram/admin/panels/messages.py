"""Message handlers for admin panel management flow."""

from __future__ import annotations

import contextlib
import re

from telethon import Button, events
from telethon.tl.custom import Message

from app import Kenzo
from app.db.crud.keyboards import KeyboardButtonCRUD
from app.db.crud.panels import PanelsManager
from app.db.crud.user import UserCRUD
from app.logger import get_logger
from app.services.panels.auth import (
    AUTH_API_KEY,
    PANEL_AUTH_PLACEHOLDER_USERNAME,
    format_exception_message,
    panel_api_error_text,
    verify_panel_api_key,
    verify_panel_password,
)
from app.services.panels.config_links import (
    parse_single_config_link_indexes,
    summarize_single_config_link_selection,
)
from app.services.panels.groups import (
    build_add_panel_group_message,
    build_group_selection_buttons,
    cache_panel_groups,
)
from app.services.panels.settings import (
    add_time_plan_to_feature_settings,
    add_volume_plan_to_feature_settings,
    get_panel_time_plan,
    get_panel_volume_plan,
    panel_node_prefixes,
    update_custom_buy_in_feature_settings,
    update_reseller_capacity_in_feature_settings,
    update_time_plan_in_feature_settings,
    update_volume_plan_in_feature_settings,
)
from app.telegram.admin.manage_user.service import delete_message
from app.telegram.admin.panels.service import (
    _is_number,
    build_panel_test_settings_content,
    display_panels,
    mutate_panel_feature_settings,
)
from app.telegram.keyboards.admin import panel_back, panel_xui_buttons
from app.telegram.keyboards.common import extract_custom_emoji_document_id
from app.telegram.keyboards.home import bhome_buttons
from app.telegram.shared.keyboards.panel_buttons import (
    build_panel_time_plan_info_buttons,
    build_panel_time_plans_admin_buttons,
    build_panel_volume_plan_info_buttons,
    build_panel_volume_plans_admin_buttons,
    create_panel_display_config_submenu,
    create_time_plan_display_config_submenu,
    create_volume_plan_display_config_submenu,
    ensure_panel_display_record,
    panel_display_config_text,
    panel_display_keyboard_key,
    panel_time_plan_info_text,
    panel_time_plans_admin_text,
    panel_volume_plan_info_text,
    panel_volume_plans_admin_text,
    time_plan_display_config_text,
    volume_plan_display_config_text,
)
from app.telegram.state import clear_user, delete_data, get_data, get_step, set_data, set_step
from app.telegram.state.store import clear_user_conversation, get_user_state, set_user_state
from app.utils.formatting.conversions import convert_storage
from app.utils.security.crypto import encrypt_data
from config import ADMIN_ID

logger = get_logger(__name__)


def _parse_stored_id(value) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


async def panel_admin_message_handler(event: Message):
    msg = (event.message.text or "").strip()
    user_id = event.sender_id
    step = await get_step(user_id)
    info = await UserCRUD().read_user(user_id)
    lang = info.language if info and info.language else "fa"

    if step == "ChangePanelUrl" and msg:
        await delete_message(event, offset=-1)
        id_panel = await get_data(event.sender_id, "ChangePanelUrl")
        new_url = msg.strip().rstrip("/")
        if not new_url:
            await event.respond(
                "❌ آدرس معتبر نیست.",
                buttons=[[Button.inline("🔙 بازگشت", data=f"panel_auth_type:{id_panel}")]],
            )
            return
        await PanelsManager().update_panel(code=id_panel, base_url=new_url)
        await event.respond(
            f"✅ آدرس پنل به‌روزرسانی شد:\n`{new_url}`\n\nایدی پنل: {id_panel}",
            buttons=[
                [Button.inline("🔐 تنظیمات ورود", data=f"panel_auth_type:{id_panel}")],
                [Button.inline("🔙 بازگشت به پنل", data=f"panel_info:{id_panel}")],
            ],
            parse_mode="markdown",
        )
        await clear_user(event.sender_id)
        await set_step(event.sender_id, "panel")
        return

    if step == "SetPanelLoginPath" and msg:
        await delete_message(event, offset=-1)
        id_panel = await get_data(event.sender_id, "SetPanelLoginPath")
        login_path = "" if msg.strip() == "-" else msg.strip().rstrip("/")
        await PanelsManager().update_panel(code=id_panel, admin_login_path=login_path)
        await event.respond(
            f"✅ مسیر ورود ادمین تنظیم شد:\n`{login_path or '(خالی — فقط base_url)'}`\n\nایدی پنل: {id_panel}",
            buttons=[Button.inline("بازگشت", data=f"panel_info:{id_panel}")],
        )
        await clear_user(event.sender_id)
        await set_step(event.sender_id, "panel")
        return

    if step == "SetPanelTunnelUrl" and msg:
        await delete_message(event, offset=-1)
        id_panel = await get_data(event.sender_id, "SetPanelTunnelUrl")
        tunnel_url = msg.strip().rstrip("/")
        await PanelsManager().update_panel(code=id_panel, tunnel_url=tunnel_url)
        await event.respond(
            f"✅ لینک تانل با موفقیت تنظیم شد:\n`{tunnel_url}`\n\nایدی پنل: {id_panel}",
            buttons=[Button.inline("بازگشت", data=f"panel_info:{id_panel}")],
        )
        await clear_user(event.sender_id)
        await set_step(event.sender_id, "panel")
        return

    if step == "ChangePanelName" and msg:
        await delete_message(event, offset=-1)
        id_panel = await get_data(event.sender_id, "ChangePanelName")
        await PanelsManager().update_panel(code=id_panel, name=msg)
        await event.respond(
            f"🍀 اسم پنل به {msg} تغییر پیدا کرد\nایدی پنل: {id_panel}",
            buttons=[Button.inline("بازگشت", data=f"panel_info:{id_panel}")],
        )
        await clear_user(event.sender_id)
        await set_step(event.sender_id, "panel")
        return

    if msg == "📚 منوی پنل ها":
        await set_step(user_id=user_id, step="Menu_panels")
        await Kenzo.send_message(entity=user_id, message="**به منوی پنل ها خوش آمدید**", buttons=panel_xui_buttons)
        return

    if msg == "🏠":
        await set_step(user_id=user_id, step="home")
        await Kenzo.send_message(
            entity=user_id,
            message="**شما برگشتید به صفحه اصلی**",
            buttons=await bhome_buttons(event.sender_id, lang),
        )
        return

    if msg == "📉 وضعیت پنل ها":
        await set_step(user_id=user_id, step="Menu_panels")
        await display_panels(user_id, current_page=1)
        return

    if msg == "▫️ افزودن پنل جدید":
        await set_step(user_id=user_id, step="addPanel_name")
        await Kenzo.send_message(
            entity=user_id,
            message="👈🏻 اسم پنل را به دلخواه وارد کنید :\n\nمثال نام : آلمان - ملی 🇩🇪\nاین اسم برای کاربران قابل مشاهده است",
            buttons=panel_back,
        )
        return

    if step == "addPanel_name" and msg not in {"🔙 بازگشت به پنل", "▫️ افزودن پنل جدید"}:
        await set_user_state(user_id, "name", msg)
        await Kenzo.send_message(
            entity=user_id,
            message=(
                "🌐 آدرس پنل را ارسال کنید.\n"
                "〰️ مثال: `https://panel.example.com`\n"
                "〰️ اگر پنل روی پورت اختصاصی است: `https://panel.example.com:8000`\n\n"
                "⚠️ فقط دامنه یا آی‌پی (و در صورت نیاز پورت) را وارد کنید؛ بدون path — مثلاً `/admin` یا هر مسیر دیگر اضافه نشود.\n\n"
                "لینک تانل یا آیپی ایران در این مرحله نیاز نیست؛ بعداً از تنظیمات همان پنل قابل تنظیم است."
            ),
        )
        await set_step(user_id, "AddPanel_url")
        return

    if step == "AddPanel_url" and msg != "🔙 بازگشت به پنل":
        await set_user_state(user_id, "url", msg.strip().rstrip("/"))
        await Kenzo.send_message(
            entity=user_id,
            message="🔐 نوع ورود به پنل را انتخاب کنید:",
            buttons=[
                [Button.inline("👤 نام کاربری و رمز", data="panel_add_auth:password")],
                [Button.inline("🔑 API Key", data="panel_add_auth:api_key")],
            ],
        )
        await set_step(user_id, "AddPanel_auth_type")
        return

    if step == "AddPanel_username" and msg != "🔙 بازگشت به پنل":
        await set_user_state(user_id, "username", msg)
        await Kenzo.send_message(entity=user_id, message="رمز پنل رو ارسال کنید")
        await set_step(user_id, "AddPanel_password")
        return

    if step == "AddPanel_password" and msg != "🔙 بازگشت به پنل":
        await set_user_state(user_id, "password", msg)
        await set_user_state(user_id, "auth_type", "password")
        panel_url = await get_user_state(user_id, "url")
        panel_username = await get_user_state(user_id, "username")
        panel_password = await get_user_state(user_id, "password")

        try:
            _authed, _token, groups_resp = await verify_panel_password(panel_url, panel_username, panel_password)
            groups_data = [(group.id, group.name) for group in groups_resp.groups]
            cache_panel_groups("add", event.sender_id, groups_data)
            await set_user_state(event.sender_id, "panel_add_groups_list", groups_data)
            await set_user_state(event.sender_id, "panel_selected_groups", [])

            message = build_add_panel_group_message(groups_data, [])
            buttons = build_group_selection_buttons(
                groups_data,
                [],
                lambda gid: f"panel_add_group_toggle:{gid}",
                "panel_add_group_confirm",
                "panel_add_group_cancel",
                "panel_add_group_select_all",
            )
            await Kenzo.send_message(entity=event.sender_id, message=message, buttons=buttons)
            await set_step(event.sender_id, "AddPanel_select_group")
        except Exception as e:
            detail = format_exception_message(e)
            await event.respond(panel_api_error_text(e))
            await clear_user_conversation(user_id)
            await set_step(event.sender_id, "panel")
            logger.exception("Add panel error: %s", detail)
        return

    if step == "AddPanel_api_key" and msg != "🔙 بازگشت به پنل":
        await set_user_state(user_id, "api_key", msg)
        await set_user_state(user_id, "auth_type", "api_key")
        panel_url = await get_user_state(user_id, "url")
        api_key = msg.strip()

        try:
            _authed, groups_resp = await verify_panel_api_key(panel_url, api_key)
            groups_data = [(group.id, group.name) for group in groups_resp.groups]
            cache_panel_groups("add", event.sender_id, groups_data)
            await set_user_state(event.sender_id, "panel_add_groups_list", groups_data)
            await set_user_state(event.sender_id, "panel_selected_groups", [])

            message = build_add_panel_group_message(groups_data, [])
            buttons = build_group_selection_buttons(
                groups_data,
                [],
                lambda gid: f"panel_add_group_toggle:{gid}",
                "panel_add_group_confirm",
                "panel_add_group_cancel",
                "panel_add_group_select_all",
            )
            await Kenzo.send_message(entity=event.sender_id, message=message, buttons=buttons)
            await set_step(event.sender_id, "AddPanel_select_group")
        except Exception as e:
            detail = format_exception_message(e)
            await event.respond(panel_api_error_text(e))
            await clear_user_conversation(user_id)
            await set_step(event.sender_id, "panel")
            logger.exception("Add panel error: %s", detail)
        return

    if step == "ChangePanelAuth_username" and msg != "🔙 بازگشت به پنل":
        await set_user_state(user_id, "change_panel_auth_username", msg)
        panel_code = await get_user_state(user_id, "change_panel_auth_code")
        await Kenzo.send_message(
            entity=user_id,
            message="رمز عبور جدید پنل را ارسال کنید:",
            buttons=[[Button.inline("❌ انصراف", data=f"panel_auth_type:{panel_code}")]],
        )
        await set_step(user_id, "ChangePanelAuth_password")
        return

    if step == "ChangePanelAuth_password" and msg != "🔙 بازگشت به پنل":
        panel_code = _parse_stored_id(await get_user_state(user_id, "change_panel_auth_code"))
        panel_username = (await get_user_state(user_id, "change_panel_auth_username") or "").strip()
        panel = await PanelsManager().get_panel_by_code(panel_code) if panel_code else None
        if not panel:
            await event.respond("❌ پنل یافت نشد.")
            await clear_user_conversation(user_id)
            await set_step(user_id, "panel")
            return
        try:
            _authed, jwt_token, _groups = await verify_panel_password(panel.base_url, panel_username, msg)
            await PanelsManager().update_panel(
                panel_code,
                auth_type="password",
                username=panel_username,
                password=encrypt_data(msg.strip()),
                cookie=jwt_token,
            )
            await clear_user_conversation(user_id)
            await set_step(user_id, "panel")
            await event.respond(
                "✅ نوع ورود به نام کاربری/رمز تغییر کرد.",
                buttons=[[Button.inline("بازگشت", data=f"panel_info:{panel_code}")]],
            )
        except Exception as e:
            await event.respond(panel_api_error_text(e))
            logger.exception("Change panel auth password error: %s", format_exception_message(e))
        return

    if step == "ChangePanelAuth_api_key" and msg != "🔙 بازگشت به پنل":
        panel_code = _parse_stored_id(await get_user_state(user_id, "change_panel_auth_code"))
        panel = await PanelsManager().get_panel_by_code(panel_code) if panel_code else None
        if not panel:
            await event.respond("❌ پنل یافت نشد.")
            await clear_user_conversation(user_id)
            await set_step(user_id, "panel")
            return
        api_key = msg.strip()
        try:
            _authed, _groups = await verify_panel_api_key(panel.base_url, api_key)
            await PanelsManager().update_panel(
                panel_code,
                auth_type=AUTH_API_KEY,
                username=PANEL_AUTH_PLACEHOLDER_USERNAME,
                password="",
                cookie=api_key,
            )
            await clear_user_conversation(user_id)
            await set_step(user_id, "panel")
            await event.respond(
                "✅ نوع ورود به API Key تغییر کرد.",
                buttons=[[Button.inline("بازگشت", data=f"panel_info:{panel_code}")]],
            )
        except Exception as e:
            await event.respond(panel_api_error_text(e))
            logger.exception("Change panel auth api_key error: %s", format_exception_message(e))
        return

    if (step or "").startswith("edit_panel_display:") and msg:
        parts = step.split(":") if step else []
        panel_code = int(parts[1]) if len(parts) >= 2 else None
        if panel_code is None:
            await event.respond("❌ پنل نامعتبر.")
            return
        panel = await PanelsManager().get_panel_by_code(code=panel_code)
        if not panel:
            await event.respond("❌ پنل یافت نشد.")
            return
        key = panel_display_keyboard_key(panel_code)
        if msg.strip().lower() == "/skip":
            await KeyboardButtonCRUD().delete_button(key)
            success = "✅ متن سفارشی حذف شد؛ از نام پنل استفاده می‌شود."
        else:
            await ensure_panel_display_record(panel)
            saved = await KeyboardButtonCRUD().set_button_text(key, msg.strip())
            success = "✅ متن ذخیره شد." if saved else "❌ خطا در ذخیره."
        btn_obj = await KeyboardButtonCRUD().get_button(key)
        prev_msg_id = await get_data(event.sender_id, "edit_panel_display_msg_id")
        body = f"{success}\n\n{panel_display_config_text(panel, btn_obj)}"
        config_buttons = create_panel_display_config_submenu(panel_code)
        if prev_msg_id:
            try:
                await Kenzo.edit_message(
                    entity=event.sender_id,
                    message=int(prev_msg_id),
                    text=body,
                    buttons=config_buttons,
                )
            except Exception:
                await event.respond(body, buttons=config_buttons)
        else:
            await event.respond(body, buttons=config_buttons)
        await delete_data(event.sender_id, "edit_panel_display_msg_id")
        await set_step(event.sender_id, "panel")
        raise events.StopPropagation

        raise events.StopPropagation

    if (step or "").startswith("add_volume_plan_storage:") and msg:
        panel_code = int(step.split(":")[1])
        if not _is_number(msg):
            await event.respond("❌ لطفاً فقط عدد وارد کنید. مثال: 10 یا 0.5")
            return
        volume = float(msg)
        if volume <= 0:
            await event.respond("❌ حجم باید بیشتر از صفر باشد.")
            return
        await set_data(user_id, "pending_volume_plan_storage", str(volume))
        await set_step(user_id, f"add_volume_plan_price:{panel_code}")
        await event.respond(
            f"💾 حجم: `{volume}` گیگ\n\n💰 قیمت را به تومان وارد کنید:",
            buttons=[[Button.inline("🔙 بازگشت", data=f"panel_volume_plans:{panel_code}")]],
        )
        return

    if (step or "").startswith("add_volume_plan_price:") and msg:
        panel_code = int(step.split(":")[1])
        normalized_price = re.sub(r"[,\s٬،]", "", msg.strip())
        if not normalized_price.isdigit() or int(normalized_price) < 0:
            await event.respond("❌ لطفاً قیمت را فقط با عدد وارد کنید.")
            return
        storage_raw = await get_data(user_id, "pending_volume_plan_storage")
        if not storage_raw:
            await event.respond("❌ خطا در دریافت حجم. دوباره از ابتدا شروع کنید.")
            await set_step(user_id, "panel")
            return
        storage_gb = float(storage_raw)
        price = int(normalized_price)

        def _add(settings):
            add_volume_plan_to_feature_settings(settings, storage_gb=storage_gb, price=price)

        if await mutate_panel_feature_settings(panel_code, _add):
            await delete_data(user_id, "pending_volume_plan_storage")
            await set_step(user_id, "panel")
            panel = await PanelsManager().get_panel_by_code(panel_code)
            await event.respond(
                f"✅ پلن حجم `{storage_gb}` گیگ با قیمت `{price:,}` تومان اضافه شد.",
                buttons=[[Button.inline("🔙 بازگشت", data=f"panel_volume_plans:{panel_code}")]],
            )
            if panel:
                text = panel_volume_plans_admin_text(panel)
                buttons = build_panel_volume_plans_admin_buttons(panel)
                await Kenzo.send_message(entity=user_id, message=text, buttons=buttons)
        else:
            await event.respond("❌ خطا در ذخیره پلن.")
        return

    if (step or "").startswith("add_time_plan_duration:") and msg:
        panel_code = int(step.split(":")[1])
        if not msg.isdigit() or int(msg) <= 0:
            await event.respond("❌ لطفاً تعداد روز را به صورت عدد صحیح وارد کنید.")
            return
        duration_days = int(msg)
        await set_data(user_id, "pending_time_plan_duration", str(duration_days))
        await set_step(user_id, f"add_time_plan_price:{panel_code}")
        await event.respond(
            f"📅 مدت: `{duration_days}` روز\n\n💰 قیمت را به تومان وارد کنید:",
            buttons=[[Button.inline("🔙 بازگشت", data=f"panel_time_plans:{panel_code}")]],
        )
        return

    if (step or "").startswith("add_time_plan_price:") and msg:
        panel_code = int(step.split(":")[1])
        normalized_price = re.sub(r"[,\s٬،]", "", msg.strip())
        if not normalized_price.isdigit() or int(normalized_price) < 0:
            await event.respond("❌ لطفاً قیمت را فقط با عدد وارد کنید.")
            return
        duration_raw = await get_data(user_id, "pending_time_plan_duration")
        if not duration_raw:
            await event.respond("❌ خطا در دریافت مدت. دوباره از ابتدا شروع کنید.")
            await set_step(user_id, "panel")
            return
        duration_days = int(duration_raw)
        price = int(normalized_price)

        def _add(settings):
            add_time_plan_to_feature_settings(settings, duration_days=duration_days, price=price)

        if await mutate_panel_feature_settings(panel_code, _add):
            await delete_data(user_id, "pending_time_plan_duration")
            await set_step(user_id, "panel")
            await event.respond(
                f"✅ پلن `{duration_days}` روزه با قیمت `{price:,}` تومان اضافه شد.",
                buttons=[[Button.inline("🔙 بازگشت", data=f"panel_time_plans:{panel_code}")]],
            )
            panel = await PanelsManager().get_panel_by_code(panel_code)
            if panel:
                await Kenzo.send_message(
                    entity=user_id,
                    message=panel_time_plans_admin_text(panel),
                    buttons=build_panel_time_plans_admin_buttons(panel),
                )
        else:
            await event.respond("❌ خطا در ذخیره پلن.")
        return

    if (step or "").startswith("edit_volume_plan_storage:") and msg:
        parts = step.split(":")
        panel_code, plan_id = int(parts[1]), int(parts[2])
        if not _is_number(msg):
            await event.respond("❌ لطفاً فقط عدد وارد کنید.")
            return
        storage_gb = float(msg)
        if storage_gb <= 0:
            await event.respond("❌ حجم باید بیشتر از صفر باشد.")
            return

        def _update(settings):
            update_volume_plan_in_feature_settings(settings, plan_id, storage_gb=storage_gb)

        if await mutate_panel_feature_settings(panel_code, _update):
            await set_step(user_id, "panel")
            panel = await PanelsManager().get_panel_by_code(panel_code)
            plan = get_panel_volume_plan(panel, plan_id)
            if panel and plan:
                await event.respond(
                    panel_volume_plan_info_text(panel, plan),
                    buttons=build_panel_volume_plan_info_buttons(panel_code, plan_id),
                )
        else:
            await event.respond("❌ خطا در ذخیره.")
        return

    if (step or "").startswith("edit_volume_plan_price:") and msg:
        parts = step.split(":")
        panel_code, plan_id = int(parts[1]), int(parts[2])
        normalized_price = re.sub(r"[,\s٬،]", "", msg.strip())
        if not normalized_price.isdigit() or int(normalized_price) < 0:
            await event.respond("❌ لطفاً قیمت را فقط با عدد وارد کنید.")
            return
        price = int(normalized_price)

        def _update(settings):
            update_volume_plan_in_feature_settings(settings, plan_id, price=price)

        if await mutate_panel_feature_settings(panel_code, _update):
            await set_step(user_id, "panel")
            panel = await PanelsManager().get_panel_by_code(panel_code)
            plan = get_panel_volume_plan(panel, plan_id)
            if panel and plan:
                await event.respond(
                    panel_volume_plan_info_text(panel, plan),
                    buttons=build_panel_volume_plan_info_buttons(panel_code, plan_id),
                )
        else:
            await event.respond("❌ خطا در ذخیره.")
        return

    if (step or "").startswith("edit_time_plan_duration:") and msg:
        parts = step.split(":")
        panel_code, plan_id = int(parts[1]), int(parts[2])
        if not msg.isdigit() or int(msg) <= 0:
            await event.respond("❌ لطفاً تعداد روز را به صورت عدد صحیح وارد کنید.")
            return
        duration_days = int(msg)

        def _update(settings):
            update_time_plan_in_feature_settings(settings, plan_id, duration_days=duration_days)

        if await mutate_panel_feature_settings(panel_code, _update):
            await set_step(user_id, "panel")
            panel = await PanelsManager().get_panel_by_code(panel_code)
            plan = get_panel_time_plan(panel, plan_id)
            if panel and plan:
                await event.respond(
                    panel_time_plan_info_text(panel, plan),
                    buttons=build_panel_time_plan_info_buttons(panel_code, plan_id),
                )
        else:
            await event.respond("❌ خطا در ذخیره.")
        return

    if (step or "").startswith("edit_time_plan_price:") and msg:
        parts = step.split(":")
        panel_code, plan_id = int(parts[1]), int(parts[2])
        normalized_price = re.sub(r"[,\s٬،]", "", msg.strip())
        if not normalized_price.isdigit() or int(normalized_price) < 0:
            await event.respond("❌ لطفاً قیمت را فقط با عدد وارد کنید.")
            return
        price = int(normalized_price)

        def _update(settings):
            update_time_plan_in_feature_settings(settings, plan_id, price=price)

        if await mutate_panel_feature_settings(panel_code, _update):
            await set_step(user_id, "panel")
            panel = await PanelsManager().get_panel_by_code(panel_code)
            plan = get_panel_time_plan(panel, plan_id)
            if panel and plan:
                await event.respond(
                    panel_time_plan_info_text(panel, plan),
                    buttons=build_panel_time_plan_info_buttons(panel_code, plan_id),
                )
        else:
            await event.respond("❌ خطا در ذخیره.")
        return

    if (step or "").startswith("edit_volume_plan_display:") and msg:
        parts = step.split(":")
        panel_code, plan_id = int(parts[1]), int(parts[2])
        display_text = "" if msg.strip().lower() == "/skip" else msg.strip()

        def _update(settings):
            update_volume_plan_in_feature_settings(settings, plan_id, display_button_text=display_text)

        if not await mutate_panel_feature_settings(panel_code, _update):
            await event.respond("❌ خطا در ذخیره.")
            return
        panel = await PanelsManager().get_panel_by_code(panel_code)
        plan = get_panel_volume_plan(panel, plan_id)
        prev_msg_id = await get_data(user_id, "edit_volume_plan_display_msg_id")
        body = f"✅ متن ذخیره شد.\n\n{volume_plan_display_config_text(panel, plan)}"
        config_buttons = create_volume_plan_display_config_submenu(panel_code, plan_id)
        if prev_msg_id:
            with contextlib.suppress(Exception):
                await Kenzo.edit_message(
                    entity=user_id,
                    message=int(prev_msg_id),
                    text=body,
                    buttons=config_buttons,
                )
        else:
            await event.respond(body, buttons=config_buttons)
        await delete_data(user_id, "edit_volume_plan_display_msg_id")
        await set_step(user_id, "panel")
        raise events.StopPropagation

    if (step or "").startswith("edit_time_plan_display:") and msg:
        parts = step.split(":")
        panel_code, plan_id = int(parts[1]), int(parts[2])
        display_text = "" if msg.strip().lower() == "/skip" else msg.strip()

        def _update(settings):
            update_time_plan_in_feature_settings(settings, plan_id, display_button_text=display_text)

        if not await mutate_panel_feature_settings(panel_code, _update):
            await event.respond("❌ خطا در ذخیره.")
            return
        panel = await PanelsManager().get_panel_by_code(panel_code)
        plan = get_panel_time_plan(panel, plan_id)
        prev_msg_id = await get_data(user_id, "edit_time_plan_display_msg_id")
        body = f"✅ متن ذخیره شد.\n\n{time_plan_display_config_text(panel, plan)}"
        config_buttons = create_time_plan_display_config_submenu(panel_code, plan_id)
        if prev_msg_id:
            with contextlib.suppress(Exception):
                await Kenzo.edit_message(
                    entity=user_id,
                    message=int(prev_msg_id),
                    text=body,
                    buttons=config_buttons,
                )
        else:
            await event.respond(body, buttons=config_buttons)
        await delete_data(user_id, "edit_time_plan_display_msg_id")
        await set_step(user_id, "panel")
        raise events.StopPropagation

    if step == "volume_plan_set_icon" and msg:
        panel_code_data = await get_data(user_id, "volume_plan_icon_panel_code")
        plan_id_data = await get_data(user_id, "volume_plan_icon_plan_id")
        panel_code = _parse_stored_id(panel_code_data)
        plan_id = _parse_stored_id(plan_id_data)
        if panel_code is None or plan_id is None:
            await event.respond("❌ پلن نامعتبر.")
            await set_step(user_id, "panel")
            return

        if msg.strip().lower() == "/skip":

            def _clear(settings):
                update_volume_plan_in_feature_settings(settings, plan_id, clear_button_icon=True)

            saved = await mutate_panel_feature_settings(panel_code, _clear)
        else:
            icon_id = extract_custom_emoji_document_id(event.message)
            if icon_id is None:
                await event.respond(
                    "❌ ایموجی پریمیوم بفرستید یا /skip.",
                    buttons=[[Button.inline("🔙 بازگشت", data=f"edit_volume_plan_display:{panel_code}:{plan_id}")]],
                )
                raise events.StopPropagation

            def _set_icon(settings):
                update_volume_plan_in_feature_settings(settings, plan_id, button_icon=icon_id)

            saved = await mutate_panel_feature_settings(panel_code, _set_icon)
        await delete_data(user_id, "volume_plan_icon_panel_code")
        await delete_data(user_id, "volume_plan_icon_plan_id")
        await set_step(user_id, "panel")
        panel = await PanelsManager().get_panel_by_code(panel_code)
        plan = get_panel_volume_plan(panel, plan_id)
        await event.respond(
            ("✅ آیکون ذخیره شد." if saved else "❌ خطا در ذخیره.")
            + f"\n\n{volume_plan_display_config_text(panel, plan)}",
            buttons=create_volume_plan_display_config_submenu(panel_code, plan_id),
        )
        raise events.StopPropagation

    if step == "time_plan_set_icon" and msg:
        panel_code_data = await get_data(user_id, "time_plan_icon_panel_code")
        plan_id_data = await get_data(user_id, "time_plan_icon_plan_id")
        panel_code = _parse_stored_id(panel_code_data)
        plan_id = _parse_stored_id(plan_id_data)
        if panel_code is None or plan_id is None:
            await event.respond("❌ پلن نامعتبر.")
            await set_step(user_id, "panel")
            return

        if msg.strip().lower() == "/skip":

            def _clear(settings):
                update_time_plan_in_feature_settings(settings, plan_id, clear_button_icon=True)

            saved = await mutate_panel_feature_settings(panel_code, _clear)
        else:
            icon_id = extract_custom_emoji_document_id(event.message)
            if icon_id is None:
                await event.respond(
                    "❌ ایموجی پریمیوم بفرستید یا /skip.",
                    buttons=[[Button.inline("🔙 بازگشت", data=f"edit_time_plan_display:{panel_code}:{plan_id}")]],
                )
                raise events.StopPropagation

            def _set_icon(settings):
                update_time_plan_in_feature_settings(settings, plan_id, button_icon=icon_id)

            saved = await mutate_panel_feature_settings(panel_code, _set_icon)
        await delete_data(user_id, "time_plan_icon_panel_code")
        await delete_data(user_id, "time_plan_icon_plan_id")
        await set_step(user_id, "panel")
        panel = await PanelsManager().get_panel_by_code(panel_code)
        plan = get_panel_time_plan(panel, plan_id)
        await event.respond(
            ("✅ آیکون ذخیره شد." if saved else "❌ خطا در ذخیره.")
            + f"\n\n{time_plan_display_config_text(panel, plan)}",
            buttons=create_time_plan_display_config_submenu(panel_code, plan_id),
        )
        raise events.StopPropagation

    if step == "panel_display_set_icon" and msg:
        panel_code_data = await get_data(event.sender_id, "panel_display_panel_code")
        panel_code = _parse_stored_id(panel_code_data)
        if panel_code is None:
            await event.respond("❌ پنل نامعتبر.")
            await set_step(event.sender_id, "panel")
            return
        panel = await PanelsManager().get_panel_by_code(code=panel_code)
        if not panel:
            await event.respond("❌ پنل یافت نشد.")
            await set_step(event.sender_id, "panel")
            return
        key = panel_display_keyboard_key(panel_code)
        if msg.strip().lower() == "/skip":
            await ensure_panel_display_record(panel)
            saved = await KeyboardButtonCRUD().set_button(key, clear_icon=True)
        else:
            icon_id = extract_custom_emoji_document_id(event.message)
            if icon_id is None:
                await event.respond(
                    "❌ ایموجی پریمیوم بفرستید یا /skip.",
                    buttons=[[Button.inline("🔙 بازگشت", data=f"edit_panel_display:{panel_code}")]],
                )
                raise events.StopPropagation
            await ensure_panel_display_record(panel)
            saved = await KeyboardButtonCRUD().set_button(key, button_icon=icon_id)
        await delete_data(event.sender_id, "panel_display_panel_code")
        await set_step(event.sender_id, "panel")
        btn_obj = await KeyboardButtonCRUD().get_button(key)
        await event.respond(
            ("✅ آیکون ذخیره شد." if saved else "❌ خطا در ذخیره.")
            + f"\n\n{panel_display_config_text(panel, btn_obj)}",
            buttons=create_panel_display_config_submenu(panel_code),
        )
        raise events.StopPropagation

    if step == "test_volume" and msg:
        if _is_number(msg):
            volume = float(msg)
            if volume <= 0:
                await event.respond("❌ حجم باید بیشتر از صفر باشد. لطفاً دوباره تلاش کنید.")
                return
            panel_code = int(await get_data(event.sender_id, "test_volume"))
            panel = await PanelsManager().get_panel_by_code(panel_code)
            if not panel:
                await event.respond("❌ پنل یافت نشد!")
                return
            await PanelsManager().update_panel(panel_code, test_volume_gb=volume)
            await event.respond(f"✅ حجم تست با موفقیت به {convert_storage(volume, for_button=True)} تغییر یافت.")
            await clear_user(event.sender_id)
            await set_step(event.sender_id, "panel")
            panel = await PanelsManager().get_panel_by_code(panel_code)
            text, buttons = await build_panel_test_settings_content(panel)
            await event.respond(text, parse_mode="html", buttons=buttons)
        else:
            await event.respond("❌ لطفاً فقط عدد وارد کنید. مثال: 2 یا 0.5")
        return

    if step == "test_duration" and msg:
        if msg.isdigit():
            duration = int(msg)
            if duration <= 0:
                await event.respond("❌ زمان باید بیشتر از صفر باشد. لطفاً دوباره تلاش کنید.")
                return
            panel_code = int(await get_data(event.sender_id, "test_duration"))
            panel = await PanelsManager().get_panel_by_code(panel_code)
            if not panel:
                await event.respond("❌ پنل یافت نشد!")
                return
            await PanelsManager().update_panel(panel_code, test_duration_days=duration)
            await event.respond(f"✅ زمان تست با موفقیت به {duration} روز تغییر یافت.")
            await clear_user(event.sender_id)
            await set_step(event.sender_id, "panel")
            panel = await PanelsManager().get_panel_by_code(panel_code)
            text, buttons = await build_panel_test_settings_content(panel)
            await event.respond(text, parse_mode="html", buttons=buttons)
        else:
            await event.respond("❌ لطفاً فقط عدد وارد کنید. مثال: 3 یا 7")
        return

    if step == "waiting_single_config_links" and msg:
        panel_code = await get_data(event.sender_id, "single_config_links_panel_code")
        if not panel_code:
            await event.respond("❌ خطا در دریافت اطلاعات پنل. لطفاً دوباره تلاش کنید.")
            await set_step(event.sender_id, "Menu_panels")
            return
        selection = msg.strip()
        if selection.lower() in {"0", "none", "off", "disable", "خاموش"}:
            selection = ""
        elif parse_single_config_link_indexes(selection) == []:
            await event.respond("❌ فرمت نامعتبر است. مثال درست: `1,2,3` یا `1-3` یا `all`")
            return
        panel_code = int(panel_code)
        await PanelsManager().update_panel(panel_code, single_config_link_indexes=selection or "")
        await clear_user(event.sender_id)
        await set_step(event.sender_id, "Menu_panels")
        status = summarize_single_config_link_selection(selection)
        await event.respond(
            f"✅ تنظیم لینک‌های تکی با موفقیت ذخیره شد.\n\n"
            f"📌 مقدار فعلی: `{status}`\n\n"
            "از این به بعد placeholder `{config_links}` و `{config_links_with_txt}` "
            "در پیام خرید سرویس و دریافت تست قابل استفاده است.",
            buttons=[[Button.inline("🔙 بازگشت به پنل", data=f"panel_info:{panel_code}")]],
        )
        return

    if step == "waiting_user_limit" and msg:
        if msg.isdigit() and int(msg) > 0:
            panel_code = await get_data(event.sender_id, "panel_user_limit_code")
            user_limit = int(msg)
            panel_manager = PanelsManager()
            await panel_manager.update_panel(panel_code, user_limit=user_limit)
            panel = await panel_manager.get_panel_by_code(panel_code)
            current_services = await panel_manager.count_panel_users(panel_code)
            await event.respond(
                f"✅ **محدودیت کانفیگ با موفقیت تنظیم شد!**\n\n"
                f"📊 پنل: {panel.name}\n"
                f"📈 تعداد کانفیگ‌های فعلی: `{current_services}`\n"
                f"🎯 محدودیت جدید: `{user_limit}`\n\n"
                f"💡 وقتی تعداد کانفیگ‌ها به {user_limit} برسد، این پنل در لیست خرید نمایش داده نخواهد شد.",
                buttons=[
                    [Button.inline("🔙 بازگشت به پنل", data=f"panel_info:{panel_code}")],
                    [Button.inline("📉 لیست پنل‌ها", data="backPanel_list")],
                ],
            )
            await clear_user(event.sender_id)
            await set_step(event.sender_id, "Menu_panels")
        else:
            await event.respond("❌ لطفاً فقط عدد صحیح مثبت وارد کنید!\n\nمثال: 100")
        return

    if step in {"waiting_custom_buy_price_gb", "waiting_custom_buy_price_day"} and msg:
        normalized_price = re.sub(r"[,\s٬،]", "", msg.strip())
        if normalized_price.isdigit() and int(normalized_price) >= 0:
            panel_code = await get_data(event.sender_id, "panel_custom_buy_code")
            if not panel_code:
                await event.respond("❌ خطا در دریافت اطلاعات پنل. لطفاً دوباره تلاش کنید.")
                await set_step(event.sender_id, "Menu_panels")
                return
            price_value = int(normalized_price)
            field = "price_per_gb" if step == "waiting_custom_buy_price_gb" else "price_per_day"
            label = "هر گیگ" if field == "price_per_gb" else "هر روز"

            def _update(settings):
                update_custom_buy_in_feature_settings(settings, **{field: price_value})

            if not await mutate_panel_feature_settings(int(panel_code), _update):
                await event.respond("❌ خطا در ذخیره تنظیمات.")
                await set_step(event.sender_id, "Menu_panels")
                return
            panel = await PanelsManager().get_panel_by_code(int(panel_code))
            await event.respond(
                f"✅ **نرخ خرید دلخواه ذخیره شد.**\n\n"
                f"📊 پنل: {panel.name if panel else panel_code}\n"
                f"💰 نرخ {label}: `{price_value:,}` تومان",
                buttons=[
                    [Button.inline("🔙 بازگشت به خرید دلخواه", data=f"panel_custom_buy:{panel_code}")],
                    [Button.inline("📉 لیست پنل‌ها", data="backPanel_list")],
                ],
            )
            await clear_user(event.sender_id)
            await set_step(event.sender_id, "Menu_panels")
        else:
            await event.respond("❌ لطفاً مبلغ را فقط با عدد وارد کنید.\n\nمثال: 5000")
        return

    if step == "waiting_reseller_capacity_price" and msg:
        normalized_price = re.sub(r"[,\s٬،]", "", msg.strip())
        if normalized_price.isdigit() and int(normalized_price) > 0:
            panel_code = await get_data(event.sender_id, "panel_reseller_capacity_code")
            if not panel_code:
                await event.respond("❌ خطا در دریافت اطلاعات پنل. لطفاً دوباره تلاش کنید.")
                await set_step(event.sender_id, "Menu_panels")
                return
            price_value = int(normalized_price)

            def _update(settings):
                update_reseller_capacity_in_feature_settings(settings, price_per_user=price_value)

            if not await mutate_panel_feature_settings(int(panel_code), _update):
                await event.respond("❌ خطا در ذخیره تنظیمات.")
                await set_step(event.sender_id, "Menu_panels")
                return
            panel = await PanelsManager().get_panel_by_code(int(panel_code))
            await event.respond(
                f"✅ **قیمت خرید ظرفیت کاربر ذخیره شد.**\n\n"
                f"📊 پنل: {panel.name if panel else panel_code}\n"
                f"💰 قیمت هر کاربر: `{price_value:,}` تومان",
                buttons=[
                    [Button.inline("🔙 بازگشت به خرید ظرفیت کاربر", data=f"panel_reseller_capacity:{panel_code}")],
                    [Button.inline("📉 لیست پنل‌ها", data="backPanel_list")],
                ],
            )
            await clear_user(event.sender_id)
            await set_step(event.sender_id, "Menu_panels")
        else:
            await event.respond("❌ لطفاً مبلغ را فقط با عدد صحیح مثبت وارد کنید.\n\nمثال: 2000")
        return

    if step == "waiting_custom_node_prefix" and msg:
        panel_code = await get_data(event.sender_id, "panel_node_prefix_panel_code")
        if not panel_code:
            await event.respond("❌ خطا در دریافت اطلاعات پنل. لطفاً دوباره تلاش کنید.")
            await set_step(event.sender_id, "start")
            return
        custom_prefix = msg.strip()
        if not custom_prefix:
            await event.respond("❌ پیشوند نمی‌تواند خالی باشد!")
            return
        panel_manager = PanelsManager()
        panel = await panel_manager.get_panel_by_code(panel_code)
        if not panel:
            await event.respond("❌ پنل یافت نشد!")
            await set_step(event.sender_id, "start")
            return
        current_prefixes = panel_node_prefixes(panel)
        if custom_prefix in current_prefixes:
            await event.respond(f"❌ پیشوند `{custom_prefix}` قبلاً اضافه شده است!")
            return
        current_prefixes.append(custom_prefix)
        new_prefixes_str = ",".join(current_prefixes)
        await panel_manager.update_panel(panel_code, node_prefixes=new_prefixes_str)
        await event.respond(
            f"✅ **پیشوند سفارشی با موفقیت اضافه شد!**\n\n"
            f"📝 پیشوند جدید: `{custom_prefix}`\n"
            f"📊 پنل: {panel.name}\n\n"
            f"💡 می‌توانید از منوی مدیریت پیشوندها برای انتخاب/لغو انتخاب آن استفاده کنید.",
            buttons=[
                [Button.inline("🔙 بازگشت به مدیریت پیشوندها", data=f"panel_node_prefixes:{panel_code}")],
                [Button.inline("📉 لیست پنل‌ها", data="backPanel_list")],
            ],
        )
        await clear_user(event.sender_id)
        await set_step(event.sender_id, "Menu_panels")
        return


def _panel_admin_message_filter(event: Message) -> bool:
    return not (event.sender_id not in ADMIN_ID or not event.is_private)


def register(client):
    client.add_event_handler(
        panel_admin_message_handler, events.NewMessage(incoming=True, func=_panel_admin_message_filter)
    )
