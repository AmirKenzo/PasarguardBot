"""Message handlers for admin plans."""

import contextlib
import re

from telethon import Button, events
from telethon.tl.custom import Message

from app import Kenzo
from app.db.crud.keyboards import KeyboardButtonCRUD
from app.db.crud.panels import PanelsManager
from app.db.crud.plans import PlanManager
from app.logger import get_logger
from app.telegram.admin.plans import states
from app.telegram.admin.plans.service import display_plan_info, is_number
from app.telegram.keyboards.common import extract_custom_emoji_document_id
from app.telegram.shared.keyboards.duration_buttons import (
    create_duration_display_config_submenu,
    duration_display_config_text,
    duration_keyboard_key,
    ensure_duration_button_record,
)
from app.telegram.shared.keyboards.plan_buttons import (
    create_plan_display_config_submenu,
    plan_display_config_text,
)
from app.telegram.state import clear_user, delete_data, get_data, get_step, set_data, set_step
from config import ADMIN_ID

logger = get_logger(__name__)


async def message_handler_plans(event: Message):
    if not event.is_private:
        return
    msg = event.message.text
    user_id = event.sender_id

    if msg == "🗞 ساخت پلن":
        buttons = [
            [Button.inline("➕ ساخت پلن جدید", data="PlanAddSelectPanel")],
            [Button.inline("📋 مدیریت پلن‌ها", data="PlanManageSelectPanel")],
            [Button.inline("❌ بستن منو ❌", data="DataCancelPlans")],
        ]
        await Kenzo.send_message(entity=user_id, message="یکی از گزینه‌های زیر را انتخاب کنید:", buttons=buttons)

    elif msg and await get_step(user_id) == "addPlan_1":
        # Delete user's message
        with contextlib.suppress(Exception):
            await Kenzo.delete_messages(user_id, [event.message.id])

        if is_number(msg):
            hajm = float(msg)
            await set_data(user_id, "addPlanHajm", msg)
            buttons = [
                [
                    Button.inline("🔙 بازگشت به منوی پلن", data="BackToPlanMainMenu"),
                    Button.inline("🔙 بازگشت", data="BackToVolumeInput"),
                ],
            ]
            # Create message with previous data
            message_text = f"💾 **حجم:** {hajm} گیگابایت\n\n"
            message_text += "📅 تعداد روز رو به عدد ( 123) وارد کنید:"

            # Edit previous volume message to show time input
            prev_msg_id = await get_data(user_id, "addPlan_volume_msg_id")
            if prev_msg_id:
                try:
                    sent_msg = await Kenzo.edit_message(
                        user_id, int(prev_msg_id), message_text, buttons=buttons, parse_mode="markdown"
                    )
                    await set_data(user_id, "addPlan_time_msg_id", str(sent_msg.id))
                except Exception:
                    # If edit fails, send new message
                    sent_msg = await event.respond(message_text, buttons=buttons, parse_mode="markdown")
                    await set_data(user_id, "addPlan_time_msg_id", str(sent_msg.id))
            else:
                sent_msg = await event.respond(message_text, buttons=buttons, parse_mode="markdown")
                await set_data(user_id, "addPlan_time_msg_id", str(sent_msg.id))
            await set_step(user_id, "addPlan_2")
        else:
            buttons = [
                [
                    Button.inline("🔙 بازگشت به منوی پلن", data="BackToPlanMainMenu"),
                    Button.inline("🔙 بازگشت", data="BackToVolumeInput"),
                ],
            ]
            # Edit previous volume message to show error
            prev_msg_id = await get_data(user_id, "addPlan_volume_msg_id")
            if prev_msg_id:
                try:
                    await Kenzo.edit_message(
                        user_id, int(prev_msg_id), "📅 فقط مجاز به ارسال عدد هستید", buttons=buttons
                    )
                except Exception:
                    await event.respond("📅 فقط مجاز به ارسال عدد هستید", buttons=buttons)
            else:
                await event.respond("📅 فقط مجاز به ارسال عدد هستید", buttons=buttons)

    elif msg and await get_step(user_id) == "addPlan_2":
        # Delete user's message
        with contextlib.suppress(Exception):
            await Kenzo.delete_messages(user_id, [event.message.id])

        if is_number(msg):
            time_days = int(msg)
            await set_data(user_id, "addPlanTime", msg)
            # Get previous data
            hajm = await get_data(user_id, "addPlanHajm")
            hajm_text = f"{float(hajm)} گیگابایت" if hajm else "تعیین نشده"

            buttons = [
                [
                    Button.inline("🔙 بازگشت به منوی پلن", data="BackToPlanMainMenu"),
                    Button.inline("🔙 بازگشت", data="BackToTimeInput"),
                ],
            ]
            # Create message with previous data
            message_text = f"💾 **حجم:** {hajm_text}\n"
            message_text += f"📅 **زمان:** {time_days} روز\n\n"
            message_text += "💰 قیمت پلن رو ارسال کنید\nمثال» 10.000"

            # Edit previous time message to show price input
            prev_msg_id = await get_data(user_id, "addPlan_time_msg_id")
            if prev_msg_id:
                try:
                    sent_msg = await Kenzo.edit_message(
                        user_id, int(prev_msg_id), message_text, buttons=buttons, parse_mode="markdown"
                    )
                    await set_data(user_id, "addPlan_price_msg_id", str(sent_msg.id))
                except Exception:
                    # If edit fails, send new message
                    sent_msg = await event.respond(message_text, buttons=buttons, parse_mode="markdown")
                    await set_data(user_id, "addPlan_price_msg_id", str(sent_msg.id))
            else:
                sent_msg = await event.respond(message_text, buttons=buttons, parse_mode="markdown")
                await set_data(user_id, "addPlan_price_msg_id", str(sent_msg.id))
            await set_step(user_id, "addPlan_3")
        else:
            buttons = [
                [
                    Button.inline("🔙 بازگشت به منوی پلن", data="BackToPlanMainMenu"),
                    Button.inline("🔙 بازگشت", data="BackToTimeInput"),
                ],
            ]
            # Edit previous time message to show error
            prev_msg_id = await get_data(user_id, "addPlan_time_msg_id")
            if prev_msg_id:
                try:
                    await Kenzo.edit_message(
                        user_id, int(prev_msg_id), "📅 فقط مجاز به ارسال عدد هستید", buttons=buttons
                    )
                except Exception:
                    await event.respond("📅 فقط مجاز به ارسال عدد هستید", buttons=buttons)
            else:
                await event.respond("📅 فقط مجاز به ارسال عدد هستید", buttons=buttons)

    elif msg and await get_step(user_id) == "addPlan_3":
        # Delete user's message
        with contextlib.suppress(Exception):
            await Kenzo.delete_messages(user_id, [event.message.id])

        if is_number(msg):
            price = int(msg)
            await set_data(user_id, "addPlanPrice", msg)
            # Get previous data
            hajm = await get_data(user_id, "addPlanHajm")
            time_days = await get_data(user_id, "addPlanTime")
            hajm_text = f"{float(hajm)} گیگابایت" if hajm else "تعیین نشده"
            time_text = f"{int(time_days)} روز" if time_days else "تعیین نشده"

            buttons = [
                [
                    Button.inline("🔙 بازگشت به منوی پلن", data="BackToPlanMainMenu"),
                    Button.inline("🔙 بازگشت", data="BackToPriceInput"),
                ],
            ]
            # Create message with previous data
            message_text = f"💾 **حجم:** {hajm_text}\n"
            message_text += f"📅 **زمان:** {time_text}\n"
            message_text += f"💰 **قیمت:** {price:,} تومان\n\n"
            message_text += "🔌 محدودیت کاربر (IP Limit) را وارد کنید:\n(0 برای نامحدود، یا عدد برای تعداد کاربر)"

            # Edit previous price message to show IP limit input
            prev_msg_id = await get_data(user_id, "addPlan_price_msg_id")
            if prev_msg_id:
                try:
                    sent_msg = await Kenzo.edit_message(
                        user_id,
                        int(prev_msg_id),
                        message_text,
                        buttons=buttons,
                        parse_mode="markdown",
                    )
                    await set_data(user_id, "addPlan_ip_limit_msg_id", str(sent_msg.id))
                except Exception:
                    # If edit fails, send new message
                    sent_msg = await event.respond(
                        message_text,
                        buttons=buttons,
                        parse_mode="markdown",
                    )
                    await set_data(user_id, "addPlan_ip_limit_msg_id", str(sent_msg.id))
            else:
                sent_msg = await event.respond(
                    message_text,
                    buttons=buttons,
                    parse_mode="markdown",
                )
                await set_data(user_id, "addPlan_ip_limit_msg_id", str(sent_msg.id))
            await set_step(user_id, "addPlan_4")
        else:
            buttons = [
                [
                    Button.inline("🔙 بازگشت به منوی پلن", data="BackToPlanMainMenu"),
                    Button.inline("🔙 بازگشت", data="BackToPriceInput"),
                ],
            ]
            # Edit previous price message to show error
            prev_msg_id = await get_data(user_id, "addPlan_price_msg_id")
            if prev_msg_id:
                try:
                    await Kenzo.edit_message(
                        user_id, int(prev_msg_id), "📅 فقط مجاز به ارسال عدد هستید", buttons=buttons
                    )
                except Exception:
                    await event.respond("📅 فقط مجاز به ارسال عدد هستید", buttons=buttons)
            else:
                await event.respond("📅 فقط مجاز به ارسال عدد هستید", buttons=buttons)

    elif msg and await get_step(user_id) == "addPlan_4":
        # Delete user's message
        with contextlib.suppress(Exception):
            await Kenzo.delete_messages(user_id, [event.message.id])

        if is_number(msg):
            hajm = await get_data(user_id, "addPlanHajm")
            timePlan = await get_data(user_id, "addPlanTime")
            price = await get_data(user_id, "addPlanPrice")
            panel_code = await get_data(user_id, "selected_panel")
            plan_type = await get_data(user_id, "plan_type")
            reset_strategy = await get_data(user_id, "reset_strategy")

            if not panel_code:
                await event.respond("❌ خطا: پنل انتخاب نشده است، لطفاً دوباره تلاش کنید.")
                return

            if not plan_type:
                plan_type = "volume"
            if not reset_strategy:
                reset_strategy = "no_reset"

            ip_limit = int(msg)
            await PlanManager().add_plan(
                price=int(price),
                storage=float(hajm),
                duration=int(timePlan),
                panel_code=int(panel_code),
                plan_type=plan_type,
                data_limit_reset_strategy=reset_strategy,
                ip_limit=ip_limit,
            )

            # Get the plan ID by finding the last added plan with these specifications
            plans = await PlanManager().get_all_plans(panel_code=int(panel_code))
            plan_id = None
            if plans:
                # Find the plan that matches our criteria (most recent one)
                matching_plans = [
                    p
                    for p in plans
                    if p.price == int(price)
                    and p.storage == float(hajm)
                    and p.duration == int(timePlan)
                    and p.plan_type == plan_type
                    and p.data_limit_reset_strategy == reset_strategy
                    and p.ip_limit == ip_limit
                ]
                if matching_plans:
                    # Get the one with highest ID (most recent)
                    plan_id = max(matching_plans, key=lambda p: p.id).id

            # Delete previous IP limit message
            prev_msg_id = await get_data(user_id, "addPlan_ip_limit_msg_id")
            if prev_msg_id:
                with contextlib.suppress(Exception):
                    await Kenzo.delete_messages(user_id, [int(prev_msg_id)])

            # Format plan type text
            plan_type_text = {
                "volume": "📊 حجمی",
                "unlimited_volume": "♾️ نامحدود حجمی",
                "fair_usage": "⚖️ مصرف منصفانه",
            }.get(plan_type, "📊 حجمی")

            # Format reset strategy text
            reset_text = {
                "no_reset": "بدون ریست",
                "day": "ریست روزانه",
                "week": "ریست هفتگی",
                "month": "ریست ماهانه",
                "year": "ریست سالانه",
            }.get(reset_strategy, "بدون ریست")

            # Format IP limit text
            ip_limit_text = "♾️ نامحدود" if ip_limit == 0 else f"👥 {ip_limit} کاربر"

            # Create beautiful success message
            success_message = "✅ **پلن جدید شما ثبت شد**\n\n"
            success_message += f"📊 **نوع پلن:** {plan_type_text}\n"
            success_message += f"💰 **قیمت:** {int(price):,} تومان\n"
            success_message += f"💾 **حجم:** {float(hajm)} گیگابایت\n"
            success_message += f"📅 **زمان:** {int(timePlan)} روز\n"
            success_message += f"🔄 **ریست:** {reset_text}\n"
            success_message += f"🔌 **محدودیت کاربر:** {ip_limit_text}"

            # Create buttons with delete option
            buttons = []
            if plan_id:
                buttons.append([Button.inline("🗑 حذف این پلن", data=f"delete_plan:{plan_id}")])
            buttons.append([Button.inline("➕ ساخت پلن جدید", data="PlanAddSelectPanel")])
            buttons.append([Button.inline("📋 مدیریت پلن‌ها", data="PlanManageSelectPanel")])
            buttons.append([Button.inline("❌ بستن منو ❌", data="DataCancelPlans")])

            await event.respond(success_message, buttons=buttons, parse_mode="markdown")
            await set_step(user_id, "panel")
            await clear_user(user_id)

        else:
            buttons = [
                [
                    Button.inline("🔙 بازگشت به منوی پلن", data="BackToPlanMainMenu"),
                    Button.inline("🔙 بازگشت", data="BackToIPLimitInput"),
                ],
            ]
            await event.respond("📅 فقط مجاز به ارسال عدد هستید", buttons=buttons)

    elif msg and await get_step(user_id) == "edit_price":
        if is_number(msg):
            plan_id = await get_data(user_id, "edit_price")
            await PlanManager().update_plan(plan_id, new_price=float(msg))
            panel_code = await get_data(user_id, "selected_panel_manage")
            message_id = await get_data(user_id, "edit_plan_message_id")

            current_page = await get_data(user_id, "plan_list_page")
            current_page = int(current_page) if current_page else 1
            await display_plan_info(
                plan_id,
                user_id,
                panel_code,
                extra_message="✅ قیمت پلن بروزرسانی شد",
                message_id=int(message_id) if message_id else None,
                show_edit_buttons=True,
                current_page=current_page,
            )
            await clear_user(user_id)
            await set_step(user_id, "panel")
        else:
            await event.respond("📅 فقط مجاز به ارسال عدد هستید")

    elif msg and await get_step(user_id) == "edit_storage":
        if is_number(msg):
            plan_id = await get_data(user_id, "edit_storage")
            await PlanManager().update_plan(plan_id, new_storage=float(msg))
            panel_code = await get_data(user_id, "selected_panel_manage")
            message_id = await get_data(user_id, "edit_plan_message_id")

            current_page = await get_data(user_id, "plan_list_page")
            current_page = int(current_page) if current_page else 1
            await display_plan_info(
                plan_id,
                user_id,
                panel_code,
                extra_message="✅ حجم پلن بروزرسانی شد",
                message_id=int(message_id) if message_id else None,
                show_edit_buttons=True,
                current_page=current_page,
            )
            await clear_user(user_id)
            await set_step(user_id, "panel")
        else:
            await event.respond("📅 فقط مجاز به ارسال عدد هستید")

    elif msg and await get_step(user_id) == "edit_duration":
        if is_number(msg):
            plan_id = await get_data(user_id, "edit_duration")
            await PlanManager().update_plan(plan_id, new_duration=int(msg))
            panel_code = await get_data(user_id, "selected_panel_manage")
            message_id = await get_data(user_id, "edit_plan_message_id")

            current_page = await get_data(user_id, "plan_list_page")
            current_page = int(current_page) if current_page else 1
            await display_plan_info(
                plan_id,
                user_id,
                panel_code,
                extra_message="✅ زمان پلن بروزرسانی شد",
                message_id=int(message_id) if message_id else None,
                show_edit_buttons=True,
                current_page=current_page,
            )
            await clear_user(user_id)
            await set_step(user_id, "panel")
        else:
            await event.respond("📅 فقط مجاز به ارسال عدد هستید")

    elif msg and await get_step(user_id) == "edit_ip_limit":
        if is_number(msg):
            plan_id = await get_data(user_id, "edit_ip_limit")
            ip_limit = int(msg)
            await PlanManager().update_plan(plan_id, new_ip_limit=ip_limit)
            panel_code = await get_data(user_id, "selected_panel_manage")
            ip_limit_text = "نامحدود" if ip_limit == 0 else f"{ip_limit} کاربر"
            message_id = await get_data(user_id, "edit_plan_message_id")

            current_page = await get_data(user_id, "plan_list_page")
            current_page = int(current_page) if current_page else 1
            await display_plan_info(
                plan_id,
                user_id,
                panel_code,
                extra_message=f"✅ محدودیت کاربر پلن به {ip_limit_text} بروزرسانی شد",
                message_id=int(message_id) if message_id else None,
                show_edit_buttons=True,
                current_page=current_page,
            )
            await clear_user(user_id)
            await set_step(user_id, "panel")
        else:
            await event.respond("📅 فقط مجاز به ارسال عدد هستید")

    elif msg and ((await get_step(user_id)) or "").startswith("edit_duration_display:"):
        step_val = await get_step(user_id)
        parts = step_val.split(":") if step_val else []
        panel_code = int(parts[1]) if len(parts) >= 2 else None
        duration = int(parts[2]) if len(parts) >= 3 else None
        if panel_code is None or duration is None:
            await event.respond("❌ داده نامعتبر.")
            return
        key = duration_keyboard_key(panel_code, duration)
        if msg.strip().lower() == "/skip":
            await KeyboardButtonCRUD().delete_button(key)
            success = "✅ متن سفارشی حذف شد."
        else:
            await ensure_duration_button_record(panel_code, duration)
            saved = await KeyboardButtonCRUD().set_button_text(key, msg.strip())
            success = "✅ متن ذخیره شد." if saved else "❌ خطا در ذخیره."
        btn_obj = await KeyboardButtonCRUD().get_button(key)
        prev_msg_id = await get_data(user_id, "edit_duration_display_msg_id")
        config_buttons = create_duration_display_config_submenu(panel_code, duration)
        body = f"{success}\n\n{duration_display_config_text(panel_code, duration, btn_obj)}"
        if prev_msg_id:
            try:
                await Kenzo.edit_message(entity=user_id, message=int(prev_msg_id), text=body, buttons=config_buttons)
            except Exception:
                await event.respond(body, buttons=config_buttons)
        else:
            await event.respond(body, buttons=config_buttons)
        await delete_data(user_id, "edit_duration_display_msg_id")
        await set_step(user_id, "panel")

    elif (msg or event.message.media) and await get_step(user_id) == "duration_btn_set_icon":
        panel_code_data = await get_data(user_id, "duration_btn_panel_code")
        duration_data = await get_data(user_id, "duration_btn_duration")
        panel_code = int(panel_code_data) if panel_code_data is not None and str(panel_code_data).isdigit() else None
        duration = int(duration_data) if duration_data is not None and str(duration_data).isdigit() else None
        if panel_code is None or duration is None:
            await event.respond("❌ داده نامعتبر.")
            await set_step(user_id, "panel")
            return
        key = duration_keyboard_key(panel_code, duration)
        if msg and msg.strip().lower() == "/skip":
            await ensure_duration_button_record(panel_code, duration)
            saved = await KeyboardButtonCRUD().set_button(key, clear_icon=True)
        else:
            icon_id = extract_custom_emoji_document_id(event.message)
            if icon_id is None:
                await event.respond(
                    "❌ ایموجی پریمیوم بفرستید یا /skip.",
                    buttons=[[Button.inline("🔙 بازگشت", data=f"edit_duration_display:{panel_code}:{duration}")]],
                )
                return
            await ensure_duration_button_record(panel_code, duration)
            saved = await KeyboardButtonCRUD().set_button(key, button_icon=icon_id)
        await delete_data(user_id, "duration_btn_panel_code")
        await delete_data(user_id, "duration_btn_duration")
        await set_step(user_id, "panel")
        btn_obj = await KeyboardButtonCRUD().get_button(key)
        await event.respond(
            ("✅ آیکون ذخیره شد." if saved else "❌ خطا در ذخیره.")
            + f"\n\n{duration_display_config_text(panel_code, duration, btn_obj)}",
            buttons=create_duration_display_config_submenu(panel_code, duration),
        )

    elif msg and ((await get_step(user_id)) or "").startswith("edit_plan_display:"):
        step_val = await get_step(user_id)
        parts = step_val.split(":") if step_val else []
        plan_id = int(parts[1]) if len(parts) >= 2 else None
        current_page = int(parts[2]) if len(parts) >= 3 else 1
        if not plan_id:
            await event.respond("❌ پلن نامعتبر است.")
            return
        plan = await PlanManager().get_plan(plan_id)
        panel = await PanelsManager().get_panel_by_code(plan.panel_code) if plan else None
        if msg.strip().lower() == "/skip":
            await PlanManager().update_plan_display(plan_id, display_button_text=None, set_display_button_text=True)
            success = "✅ متن سفارشی حذف شد؛ قالب خودکار فعال است."
        else:
            saved = await PlanManager().update_plan_display(
                plan_id, display_button_text=msg.strip(), set_display_button_text=True
            )
            success = "✅ متن دکمه ذخیره شد." if saved else "❌ خطا در ذخیره."
        plan = await PlanManager().get_plan(plan_id)
        prev_msg_id = await get_data(user_id, "edit_plan_display_msg_id")
        config_buttons = create_plan_display_config_submenu(plan_id, current_page)
        if prev_msg_id:
            try:
                await Kenzo.edit_message(
                    entity=user_id,
                    message=int(prev_msg_id),
                    text=f"{success}\n\n{plan_display_config_text(plan, panel)}",
                    buttons=config_buttons,
                )
            except Exception:
                await event.respond(f"{success}\n\n{plan_display_config_text(plan, panel)}", buttons=config_buttons)
        else:
            await event.respond(f"{success}\n\n{plan_display_config_text(plan, panel)}", buttons=config_buttons)
        await delete_data(user_id, "edit_plan_display_msg_id")
        await set_step(user_id, "panel")

    elif (msg or event.message.media) and await get_step(user_id) == "plan_btn_set_icon":
        plan_id_data = await get_data(user_id, "plan_btn_plan_id")
        page_data = await get_data(user_id, "plan_btn_page")
        plan_id = int(plan_id_data) if plan_id_data is not None and str(plan_id_data).isdigit() else None
        current_page = int(page_data) if page_data is not None and str(page_data).isdigit() else 1
        if not plan_id:
            await event.respond("❌ پلن یافت نشد.")
            await set_step(user_id, "panel")
            return
        if msg and msg.strip().lower() == "/skip":
            saved = await PlanManager().update_plan_display(plan_id, clear_button_icon=True)
        else:
            icon_id = extract_custom_emoji_document_id(event.message)
            if icon_id is None:
                await event.respond(
                    "❌ ایموجی معمولی document_id ندارد. از پنل ایموجی پریمیوم تلگرام بفرستید یا /skip.",
                    buttons=[[Button.inline("🔙 بازگشت", data=f"edit_plan_display:{plan_id}:{current_page}")]],
                )
                return
            saved = await PlanManager().update_plan_display(plan_id, button_icon=icon_id, set_button_icon=True)
        await delete_data(user_id, "plan_btn_plan_id")
        await delete_data(user_id, "plan_btn_page")
        await set_step(user_id, "panel")
        plan = await PlanManager().get_plan(plan_id)
        panel = await PanelsManager().get_panel_by_code(plan.panel_code) if plan else None
        await event.respond(
            ("✅ آیکون ذخیره شد." if saved else "❌ خطا در ذخیره.") + f"\n\n{plan_display_config_text(plan, panel)}",
            buttons=create_plan_display_config_submenu(plan_id, current_page),
        )

    elif msg and await get_step(user_id) == "bulk_update_plans":
        try:
            # Parse the message to extract plan updates
            # Format: id=1, price=123, data_limit=10, time=30, ip_limit=1
            lines = msg.strip().split("\n")
            updates = []
            errors = []

            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                # Skip empty lines and header lines
                if (
                    not line
                    or line.startswith("✏️")
                    or line.startswith("📝")
                    or line.startswith("**")
                    or line.startswith("=")
                    or "id=" not in line
                ):
                    continue

                # Remove markdown code formatting if present
                line = line.replace("`", "").strip()

                try:
                    # Parse format: id=1, price=123, data_limit=10, time=30, ip_limit=1
                    plan_id = None
                    price = None
                    data_limit = None
                    time = None
                    ip_limit = None

                    # Clean up the line: remove extra commas and normalize
                    # Replace patterns like "data_limit=,35" with "data_limit=35"
                    line = re.sub(r"=\s*,", "=", line)
                    # Replace patterns like "35 time=" with "35, time="
                    line = re.sub(r"(\d+)\s+(\w+=)", r"\1, \2", line)

                    # Split by comma and parse each part
                    parts = [p.strip() for p in line.split(",")]
                    for part in parts:
                        part = part.strip()
                        if "=" not in part:
                            continue

                        key, value = [p.strip() for p in part.split("=", 1)]

                        # Skip if value is empty
                        if not value:
                            continue

                        # Remove any remaining commas from value
                        value = value.rstrip(",").strip()

                        if not value:
                            continue

                        try:
                            if key == "id":
                                plan_id = int(value)
                            elif key == "price":
                                price = float(value)
                            elif key == "data_limit":
                                data_limit = int(float(value))  # Convert to int
                            elif key == "time":
                                time = int(value)
                            elif key == "ip_limit":
                                ip_limit = int(value)
                        except ValueError, TypeError:
                            # Skip invalid values but continue parsing other fields
                            continue

                    # Validate required fields
                    if plan_id is None:
                        errors.append(f"خط {line_num}: id مشخص نشده است")
                        continue

                    # Validate values
                    if data_limit is not None and data_limit <= 0:
                        errors.append(f"خط {line_num}: data_limit باید بیشتر از صفر باشد")
                        continue
                    if price is not None and price < 0:
                        errors.append(f"خط {line_num}: price نمی‌تواند منفی باشد")
                        continue
                    if time is not None and time <= 0:
                        errors.append(f"خط {line_num}: time باید بیشتر از صفر باشد")
                        continue
                    if ip_limit is not None and ip_limit < 0:
                        errors.append(f"خط {line_num}: ip_limit نمی‌تواند منفی باشد")
                        continue

                    update_data = {"plan_id": plan_id}
                    if price is not None:
                        update_data["price"] = price
                    if data_limit is not None:
                        update_data["storage"] = data_limit
                    if time is not None:
                        update_data["duration"] = time
                    if ip_limit is not None:
                        update_data["ip_limit"] = ip_limit

                    updates.append(update_data)
                except (ValueError, IndexError) as e:
                    errors.append(f"خط {line_num}: خطا در پارس کردن داده‌ها - {e!s}")
                    continue

            if not updates:
                await event.respond("❌ هیچ داده‌ای برای به‌روزرسانی پیدا نشد. لطفاً فرمت را بررسی کنید.")
                return

            # Get message ID to delete the previous message
            message_id = await get_data(user_id, "bulk_update_plans_message_id")
            panel_code = await get_data(user_id, "bulk_update_plans_panel_code")

            # Perform bulk update
            result = await PlanManager().bulk_update_plans(updates)

            if result["success"]:
                success_msg = "✅ **به‌روزرسانی گروهی انجام شد**\n\n"
                success_msg += f"📊 تعداد پلن‌های به‌روزرسانی شده: {result['updated_count']}\n"

                if result.get("changed_plans"):
                    success_msg += "\n**📝 پلن‌های تغییر کرده:**\n\n"
                    success_msg += "```\n"
                    for changed_plan in result["changed_plans"]:
                        plan_id = changed_plan["plan_id"]
                        new_vals = changed_plan["new_values"]
                        old_vals = changed_plan["old_values"]

                        changes = []
                        if "price" in new_vals:
                            changes.append(f"price: {int(old_vals['price'])} → {int(new_vals['price'])}")
                        if "storage" in new_vals:
                            changes.append(f"data_limit: {int(old_vals['storage'])} → {int(new_vals['storage'])}")
                        if "duration" in new_vals:
                            changes.append(f"time: {old_vals['duration']} → {new_vals['duration']}")
                        if "ip_limit" in new_vals:
                            changes.append(f"ip_limit: {old_vals['ip_limit']} → {new_vals['ip_limit']}")

                        success_msg += f"ID {plan_id}: {', '.join(changes)}\n"
                    success_msg += "```"

                if result["errors"]:
                    success_msg += "\n\n⚠️ **خطاها:**\n"
                    for error in result["errors"][:10]:  # Show first 10 errors
                        success_msg += f"• {error}\n"
                    if len(result["errors"]) > 10:
                        success_msg += f"... و {len(result['errors']) - 10} خطای دیگر\n"

                # Delete previous message if exists
                if message_id:
                    try:
                        await Kenzo.delete_messages(user_id, [int(message_id)])
                    except Exception as e:
                        logger.error(f"Error deleting previous message: {e}")

                # Add back button
                buttons = []
                if panel_code:
                    buttons = [
                        [Button.inline("🔙 بازگشت", data=f"ManagePlans_{panel_code}")],
                    ]

                await event.respond(success_msg, parse_mode="markdown", buttons=buttons if buttons else None)
            else:
                error_msg = "❌ **خطا در به‌روزرسانی گروهی**\n\n"
                for error in result["errors"][:10]:
                    error_msg += f"• {error}\n"
                await event.respond(error_msg, parse_mode="markdown")

            # Clean up
            await clear_user(user_id)
            await set_step(user_id, "panel")

        except Exception as e:
            logger.error(f"Error in bulk update plans: {e}")
            await event.respond(f"❌ خطا در پردازش: {e!s}")


async def _plans_message_filter(event: Message) -> bool:
    if event.sender_id not in ADMIN_ID or not event.is_private:
        return False
    msg = (event.message.text or "").strip()
    if msg == states.PLAN_MENU_MESSAGE:
        return True
    step = (await get_step(event.sender_id)) or ""
    if step in states.ICON_STEPS and (msg or event.message.media):
        return True
    if step in states.PLAN_INPUT_STEPS and msg:
        return True
    if step.startswith("edit_duration_display:") and msg:
        return True
    return bool(step.startswith("edit_plan_display:") and msg)


def register(client):
    client.add_event_handler(
        message_handler_plans,
        events.NewMessage(incoming=True, from_users=ADMIN_ID, func=_plans_message_filter),
    )
