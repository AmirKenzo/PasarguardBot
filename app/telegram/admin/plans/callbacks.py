"""Callback handlers for admin plans."""

import contextlib

from telethon import Button, events

from app import Kenzo
from app.db.crud.keyboards import KeyboardButtonCRUD
from app.db.crud.panels import PanelsManager
from app.db.crud.plans import PlanManager
from app.logger import get_logger
from app.services.panels.settings import panel_display_mode
from app.telegram.admin.plans.service import display_plan_info, display_plans
from app.telegram.keyboards.registry import STYLE_LABELS
from app.telegram.shared.keyboards.duration_buttons import (
    build_manage_duration_buttons_view,
    cleanup_all_orphan_duration_buttons,
    cleanup_duration_button_after_plan_delete,
    create_duration_display_config_submenu,
    duration_display_config_text,
    duration_keyboard_key,
    ensure_duration_button_record,
    get_orphan_duration_values,
)
from app.telegram.shared.keyboards.plan_buttons import (
    build_default_plan_button_text,
    create_plan_display_config_submenu,
    plan_display_config_text,
)
from app.telegram.shared.utils.maintenance import bot_is_offline
from app.telegram.state import clear_user, delete_data, get_data, set_data, set_step
from config import ADMIN_ID

logger = get_logger(__name__)


@bot_is_offline
async def inline_callback(event: events.CallbackQuery.Event):
    if not event.is_private:
        return
    data = event.data.decode("utf-8")
    user_id = event.sender_id

    if data == "PlanAddSelectPanel":
        panels = await PanelsManager().get_all_panels()  # Show all panels including disabled ones
        if not panels:
            await event.respond("❌ پنلی وجود ندارد")
            return
        # Show panel status in button text
        panel_buttons = [
            [Button.inline(f"{'✅' if panel.enable == 1 else '❌'} {panel.name}", data=f"AddPlans_{panel.code}")]
            for panel in panels
        ]
        panel_buttons.append([Button.inline("🔙 بازگشت", data="BackToPlanMainMenu")])
        await event.edit("لطفاً پنل مورد نظر خود را انتخاب کنید:", buttons=panel_buttons)

    elif data == "PlanManageSelectPanel":
        panels = await PanelsManager().get_all_panels()  # Show all panels including disabled ones
        if not panels:
            await event.respond("❌ پنلی وجود ندارد")
            return
        # Show panel status in button text
        panel_buttons = [
            [Button.inline(f"{'✅' if panel.enable == 1 else '❌'} {panel.name}", data=f"ManagePlans_{panel.code}")]
            for panel in panels
        ]
        panel_buttons.append([Button.inline("🔙 بازگشت", data="BackToPlanMainMenu")])
        await event.edit("لطفاً پنل مورد نظر را انتخاب کنید:", buttons=panel_buttons)

    elif data == "BackToPlanMainMenu":
        # Clear all plan creation steps to prevent confusion
        await delete_data(user_id, "addPlanHajm")
        await delete_data(user_id, "addPlanTime")
        await delete_data(user_id, "addPlanPrice")
        await delete_data(user_id, "plan_type")
        await delete_data(user_id, "reset_strategy")
        await delete_data(user_id, "selected_panel")
        await delete_data(user_id, "addPlan_volume_msg_id")
        await delete_data(user_id, "addPlan_time_msg_id")
        await delete_data(user_id, "addPlan_price_msg_id")
        await delete_data(user_id, "addPlan_ip_limit_msg_id")
        # Reset user step to panel to prevent accepting numbers
        await set_step(user_id, "panel")

        # Return to main plan menu
        buttons = [
            [Button.inline("➕ ساخت پلن جدید", data="PlanAddSelectPanel")],
            [Button.inline("📋 مدیریت پلن‌ها", data="PlanManageSelectPanel")],
            [Button.inline("❌ بستن منو ❌", data="DataCancelPlans")],
        ]
        await event.edit("یکی از گزینه‌های زیر را انتخاب کنید:", buttons=buttons)

    elif data.startswith("ManagePlans_"):
        panel_code = data.split("_")[1]
        await set_data(user_id, "selected_panel_manage", panel_code)

        buttons = [
            [Button.inline("✏️ اپدیت همه پلن‌ها با تکست", data=f"UpdateAllPlans_{panel_code}")],
            [Button.inline("📄 لیست پلن‌ها (صفحه‌بندی)", data=f"ListPlans_{panel_code}")],
            [Button.inline("📊 دریافت لیست قیمت‌ها", data=f"GetPlansPriceList_{panel_code}")],
        ]
        panel = await PanelsManager().get_panel_by_code(int(panel_code))
        if panel and panel_display_mode(panel) == "duration_first":
            buttons.append([Button.inline("🎨 دکمه‌های مدت (زمان اول)", data=f"ManageDurationButtons_{panel_code}")])
        buttons.append([Button.inline("🔙 بازگشت", data="PlanManageSelectPanel")])
        await event.edit("لطفاً یکی از گزینه‌های زیر را انتخاب کنید:", buttons=buttons)

    elif data.startswith("ManageDurationButtons_"):
        panel_code = int(data.split("_")[1])
        active = await PlanManager().get_unique_durations(panel_code)
        if not active and not await get_orphan_duration_values(panel_code):
            await event.answer("❌ هیچ مدت و تنظیماتی برای این پنل یافت نشد.", alert=True)
            return
        message_text, rows = await build_manage_duration_buttons_view(panel_code)
        await event.edit(message_text, buttons=rows)

    elif data.startswith("delete_orphan_duration:"):
        parts = data.split(":")
        panel_code = int(parts[1])
        duration = int(parts[2])
        deleted = await KeyboardButtonCRUD().delete_button(duration_keyboard_key(panel_code, duration))
        await event.answer("✅ تنظیمات حذف شد." if deleted else "❌ رکوردی یافت نشد.", alert=True)
        message_text, rows = await build_manage_duration_buttons_view(panel_code)
        await event.edit(message_text, buttons=rows)

    elif data.startswith("CleanupOrphanDurationButtons_"):
        panel_code = int(data.split("_")[1])
        deleted_count = await cleanup_all_orphan_duration_buttons(panel_code)
        await event.answer(
            f"✅ {deleted_count} تنظیم بدون پلن حذف شد." if deleted_count else "چیزی برای حذف نبود.",
            alert=True,
        )
        message_text, rows = await build_manage_duration_buttons_view(panel_code)
        await event.edit(message_text, buttons=rows)

    elif data.startswith("edit_duration_display:"):
        parts = data.split(":")
        panel_code = int(parts[1])
        duration = int(parts[2])
        keyboard_crud = KeyboardButtonCRUD()
        btn_obj = await keyboard_crud.get_button(duration_keyboard_key(panel_code, duration))
        await set_data(user_id, "edit_duration_display_msg_id", str(event.original_update.msg_id))
        await event.edit(
            duration_display_config_text(panel_code, duration, btn_obj),
            buttons=create_duration_display_config_submenu(panel_code, duration),
        )

    elif data.startswith("duration_btn_edit_text:"):
        parts = data.split(":")
        panel_code = int(parts[1])
        duration = int(parts[2])
        keyboard_crud = KeyboardButtonCRUD()
        btn_obj = await keyboard_crud.get_button(duration_keyboard_key(panel_code, duration))
        current = btn_obj.button_text if btn_obj and btn_obj.button_text else f"📅 {duration} روزه"
        await set_step(user_id, f"edit_duration_display:{panel_code}:{duration}")
        await set_data(user_id, "edit_duration_display_msg_id", str(event.original_update.msg_id))
        await event.edit(
            f"📝 متن فعلی دکمه **{duration} روزه**:\n<blockquote expandable>{current}</blockquote>\n\n"
            "متن جدید را ارسال کنید یا /skip برای قالب پیش‌فرض:",
            buttons=[[Button.inline("🔙 بازگشت", data=f"edit_duration_display:{panel_code}:{duration}")]],
            parse_mode="html",
        )

    elif data.startswith("duration_btn_color:"):
        parts = data.split(":")
        if len(parts) < 4:
            await event.answer("❌ درخواست نامعتبر", alert=True)
            return
        panel_code = int(parts[1])
        duration = int(parts[2])
        style_val = parts[3]
        key = duration_keyboard_key(panel_code, duration)
        await ensure_duration_button_record(panel_code, duration)
        keyboard_crud = KeyboardButtonCRUD()
        if style_val == "none":
            await keyboard_crud.set_button(key, button_style="")
            await event.answer("رنگ حذف شد.")
        else:
            await keyboard_crud.set_button(key, button_style=style_val)
            await event.answer("رنگ تنظیم شد.")
        btn_obj = await keyboard_crud.get_button(key)
        await event.edit(
            duration_display_config_text(panel_code, duration, btn_obj),
            buttons=create_duration_display_config_submenu(panel_code, duration),
        )

    elif data.startswith("duration_btn_icon:"):
        parts = data.split(":")
        panel_code = int(parts[1])
        duration = int(parts[2])
        await set_data(user_id, "duration_btn_panel_code", str(panel_code))
        await set_data(user_id, "duration_btn_duration", str(duration))
        await set_step(user_id, "duration_btn_set_icon")
        await event.edit(
            "📎 آیدی ایموجی پریمیوم را بفرستید یا /skip برای حذف:",
            buttons=[[Button.inline("🔙 بازگشت", data=f"edit_duration_display:{panel_code}:{duration}")]],
        )

    elif data.startswith("duration_btn_icon_clear:"):
        parts = data.split(":")
        panel_code = int(parts[1])
        duration = int(parts[2])
        key = duration_keyboard_key(panel_code, duration)
        await KeyboardButtonCRUD().set_button(key, clear_icon=True)
        await event.answer("آیکون حذف شد.")
        btn_obj = await KeyboardButtonCRUD().get_button(key)
        await event.edit(
            duration_display_config_text(panel_code, duration, btn_obj),
            buttons=create_duration_display_config_submenu(panel_code, duration),
        )

    elif data.startswith("duration_btn_display_reset:"):
        parts = data.split(":")
        panel_code = int(parts[1])
        duration = int(parts[2])
        key = duration_keyboard_key(panel_code, duration)
        await KeyboardButtonCRUD().delete_button(key)
        await event.answer("تنظیمات ریست شد.")
        active = await PlanManager().get_unique_durations(panel_code)
        if duration not in active:
            message_text, rows = await build_manage_duration_buttons_view(panel_code)
            await event.edit(message_text, buttons=rows)
        else:
            await event.edit(
                duration_display_config_text(panel_code, duration, None),
                buttons=create_duration_display_config_submenu(panel_code, duration),
            )

    elif data.startswith("PrevPlan:") or data.startswith("NextPlan:"):
        parts = data.split(":")
        panel_code = parts[1]
        current_page = int(parts[2])
        plans = await PlanManager().get_all_plans(panel_code=panel_code)
        plans = sorted(plans, key=lambda p: p.storage)
        total_plans = len(plans)
        PANEL_LIMIT = 10
        num_pages = (total_plans + PANEL_LIMIT - 1) // PANEL_LIMIT

        if data.startswith("PrevPlan:") and current_page > 1:
            current_page -= 1
        elif data.startswith("NextPlan:") and current_page < num_pages:
            current_page += 1

        current_page = max(1, min(current_page, num_pages))
        await set_data(user_id, "plan_list_page", str(current_page))
        await display_plans(user_id, panel_code, current_page, edit_message=True, original_event=event)

    elif data.startswith("plan_info:"):
        parts = data.split(":")
        plan_id = int(parts[1])
        current_page = int(parts[2]) if len(parts) > 2 else 1
        panel_code = await get_data(user_id, "selected_panel_manage")
        await set_data(user_id, "plan_list_page", str(current_page))
        await display_plan_info(
            plan_id, user_id, panel_code, edit_message=True, original_event=event, current_page=current_page
        )

    elif data.startswith("edit_plan_display:"):
        parts = data.split(":")
        plan_id = int(parts[1])
        current_page = int(parts[2]) if len(parts) > 2 else 1
        plan = await PlanManager().get_plan(plan_id)
        if not plan:
            await event.answer("پلن یافت نشد!", alert=True)
            return
        panel = await PanelsManager().get_panel_by_code(plan.panel_code)
        await set_data(user_id, "edit_plan_display_msg_id", str(event.original_update.msg_id))
        await event.edit(
            plan_display_config_text(plan, panel),
            buttons=create_plan_display_config_submenu(plan_id, current_page),
        )

    elif data.startswith("plan_btn_edit_text:"):
        parts = data.split(":")
        plan_id = int(parts[1])
        current_page = int(parts[2]) if len(parts) > 2 else 1
        plan = await PlanManager().get_plan(plan_id)
        if not plan:
            await event.answer("پلن یافت نشد!", alert=True)
            return
        panel = await PanelsManager().get_panel_by_code(plan.panel_code)

        current = plan.display_button_text or build_default_plan_button_text(plan, panel_display_mode(panel), "buy")
        await set_step(user_id, f"edit_plan_display:{plan_id}:{current_page}")
        await set_data(user_id, "edit_plan_display_msg_id", str(event.original_update.msg_id))
        await event.edit(
            f"📝 متن فعلی دکمه پلن #{plan_id}:\n<blockquote expandable>{current}</blockquote>\n\n"
            "متن جدید را ارسال کنید یا /skip برای بازگشت به قالب خودکار:",
            buttons=[[Button.inline("🔙 بازگشت", data=f"edit_plan_display:{plan_id}:{current_page}")]],
            parse_mode="html",
        )

    elif data.startswith("plan_btn_color:"):
        parts = data.split(":")
        if len(parts) < 4:
            await event.answer("❌ درخواست نامعتبر است.", alert=True)
            return
        plan_id = int(parts[1])
        current_page = int(parts[2])
        style_val = parts[3]
        plan = await PlanManager().get_plan(plan_id)
        if not plan:
            await event.answer("پلن یافت نشد!", alert=True)
            return
        panel = await PanelsManager().get_panel_by_code(plan.panel_code)

        if style_val == "none":
            await PlanManager().update_plan_display(plan_id, button_style="", set_button_style=True)
            await event.answer("رنگ دکمه حذف شد.")
        else:
            await PlanManager().update_plan_display(plan_id, button_style=style_val, set_button_style=True)
            await event.answer(f"رنگ تغییر کرد به {STYLE_LABELS.get(style_val, style_val)}.")
        plan = await PlanManager().get_plan(plan_id)
        await event.edit(
            plan_display_config_text(plan, panel),
            buttons=create_plan_display_config_submenu(plan_id, current_page),
        )

    elif data.startswith("plan_btn_icon:"):
        parts = data.split(":")
        plan_id = int(parts[1])
        current_page = int(parts[2]) if len(parts) > 2 else 1
        await set_data(user_id, "plan_btn_plan_id", str(plan_id))
        await set_data(user_id, "plan_btn_page", str(current_page))
        await set_step(user_id, "plan_btn_set_icon")
        await event.edit(
            "📎 آیدی سند ایموجی پریمیوم را بفرستید یا /skip برای حذف:",
            buttons=[[Button.inline("🔙 بازگشت", data=f"edit_plan_display:{plan_id}:{current_page}")]],
        )

    elif data.startswith("plan_btn_icon_clear:"):
        parts = data.split(":")
        plan_id = int(parts[1])
        current_page = int(parts[2]) if len(parts) > 2 else 1
        plan = await PlanManager().get_plan(plan_id)
        if not plan:
            await event.answer("پلن یافت نشد!", alert=True)
            return
        panel = await PanelsManager().get_panel_by_code(plan.panel_code)
        await PlanManager().update_plan_display(plan_id, clear_button_icon=True)
        await event.answer("آیکون دکمه حذف شد.")
        plan = await PlanManager().get_plan(plan_id)
        await event.edit(
            plan_display_config_text(plan, panel),
            buttons=create_plan_display_config_submenu(plan_id, current_page),
        )

    elif data.startswith("plan_btn_display_reset:"):
        parts = data.split(":")
        plan_id = int(parts[1])
        current_page = int(parts[2]) if len(parts) > 2 else 1
        if await PlanManager().reset_plan_display_button(plan_id):
            await event.answer("تنظیمات نمایش پلن ریست شد.")
        else:
            await event.answer("خطا در ریست.", alert=True)
            return
        plan = await PlanManager().get_plan(plan_id)
        panel = await PanelsManager().get_panel_by_code(plan.panel_code)
        await event.edit(
            plan_display_config_text(plan, panel),
            buttons=create_plan_display_config_submenu(plan_id, current_page),
        )

    elif data.startswith("BackToPlanList:"):
        parts = data.split(":")
        panel_code = parts[1]
        current_page = int(parts[2]) if len(parts) > 2 else 1
        await display_plans(user_id, panel_code, current_page=current_page, edit_message=True, original_event=event)

    elif data.startswith("edit_price:"):
        plan_id = int(data.split(":")[1])
        panel_code = await get_data(user_id, "selected_panel_manage")
        current_page = await get_data(user_id, "plan_list_page")
        current_page = int(current_page) if current_page else 1
        await set_data(user_id, "edit_price", plan_id)
        await set_data(user_id, "edit_plan_message_id", str(event.original_update.msg_id))
        await display_plan_info(
            plan_id,
            user_id,
            panel_code,
            edit_message=True,
            original_event=event,
            extra_message="💬 قیمت جدید را وارد کنید:",
            show_edit_buttons=False,
            current_page=current_page,
        )
        await set_step(user_id, "edit_price")

    elif data.startswith("edit_storage:"):
        plan_id = int(data.split(":")[1])
        panel_code = await get_data(user_id, "selected_panel_manage")
        current_page = await get_data(user_id, "plan_list_page")
        current_page = int(current_page) if current_page else 1
        await set_data(user_id, "edit_storage", plan_id)
        await set_data(user_id, "edit_plan_message_id", str(event.original_update.msg_id))
        await display_plan_info(
            plan_id,
            user_id,
            panel_code,
            edit_message=True,
            original_event=event,
            extra_message="💬 حجم جدید (گیگابایت) را وارد کنید:",
            show_edit_buttons=False,
            current_page=current_page,
        )
        await set_step(user_id, "edit_storage")

    elif data.startswith("edit_duration:"):
        plan_id = int(data.split(":")[1])
        panel_code = await get_data(user_id, "selected_panel_manage")
        current_page = await get_data(user_id, "plan_list_page")
        current_page = int(current_page) if current_page else 1
        await set_data(user_id, "edit_duration", plan_id)
        await set_data(user_id, "edit_plan_message_id", str(event.original_update.msg_id))
        await display_plan_info(
            plan_id,
            user_id,
            panel_code,
            edit_message=True,
            original_event=event,
            extra_message="💬 مدت زمان جدید (روز) را وارد کنید:",
            show_edit_buttons=False,
            current_page=current_page,
        )
        await set_step(user_id, "edit_duration")

    elif data.startswith("edit_ip_limit:"):
        plan_id = int(data.split(":")[1])
        panel_code = await get_data(user_id, "selected_panel_manage")
        current_page = await get_data(user_id, "plan_list_page")
        current_page = int(current_page) if current_page else 1
        await set_data(user_id, "edit_ip_limit", plan_id)
        await set_data(user_id, "edit_plan_message_id", str(event.original_update.msg_id))
        await display_plan_info(
            plan_id,
            user_id,
            panel_code,
            edit_message=True,
            original_event=event,
            extra_message="💬 محدودیت کاربر جدید را وارد کنید:\n(0 برای نامحدود، یا عدد برای تعداد کاربر)",
            show_edit_buttons=False,
            current_page=current_page,
        )
        await set_step(user_id, "edit_ip_limit")

    elif data.startswith("delete_plan:"):
        plan_id = int(data.split(":")[1])

        # Get plan info before deleting to know panel_code
        plan = await PlanManager().get_plan(plan_id)
        plan_panel_code = plan.panel_code if plan else None
        plan_duration = plan.duration if plan else None

        await PlanManager().delete_plan(plan_id)
        if plan_panel_code is not None and plan_duration is not None:
            await cleanup_duration_button_after_plan_delete(plan_panel_code, plan_duration)
        await event.answer("✅ پلن حذف شد", alert=True)

        # Check if we came from plan list (via plan_info page)
        panel_code = await get_data(user_id, "selected_panel_manage")
        current_page = await get_data(user_id, "plan_list_page")

        # If panel_code from step manager exists and matches plan's panel_code, return to list
        if panel_code and current_page and plan_panel_code and int(panel_code) == plan_panel_code:
            # Came from plan list, return to the same page
            panel_code = int(panel_code)
            current_page = int(current_page)

            # Check if there are still plans left
            plans = await PlanManager().get_all_plans(panel_code=panel_code)
            if plans:
                # Recalculate page number in case current page is now empty
                plans = sorted(plans, key=lambda p: p.storage)
                total_plans = len(plans)
                PANEL_LIMIT = 20
                num_pages = (total_plans + PANEL_LIMIT - 1) // PANEL_LIMIT
                # If current page is beyond available pages, go to last page
                if current_page > num_pages:
                    current_page = num_pages if num_pages > 0 else 1
                await set_data(user_id, "plan_list_page", str(current_page))
                await display_plans(
                    user_id, panel_code, current_page=current_page, edit_message=True, original_event=event
                )
            else:
                # No plans left, go to manage panel menu
                buttons = [
                    [Button.inline("➕ ساخت پلن جدید", data="PlanAddSelectPanel")],
                    [Button.inline("📋 مدیریت پلن‌ها", data="PlanManageSelectPanel")],
                    [Button.inline("❌ بستن منو ❌", data="DataCancelPlans")],
                ]
                await event.edit(
                    "✅ پلن با موفقیت حذف شد\n\nهیچ پلنی باقی نمانده است.\n\nیکی از گزینه‌های زیر را انتخاب کنید:",
                    buttons=buttons,
                )
        else:
            # Came from add plan page, show add plan menu
            buttons = [
                [Button.inline("➕ ساخت پلن جدید", data="PlanAddSelectPanel")],
                [Button.inline("📋 مدیریت پلن‌ها", data="PlanManageSelectPanel")],
                [Button.inline("❌ بستن منو ❌", data="DataCancelPlans")],
            ]
            await event.edit("✅ پلن با موفقیت حذف شد\n\nیکی از گزینه‌های زیر را انتخاب کنید:", buttons=buttons)

    elif data.startswith("AddPlans_"):
        panel_code = data.split("_")[1]
        await set_data(user_id, "selected_panel", panel_code)

        buttons = [
            [Button.inline("📊 پلن حجمی", data="PlanType_volume")],
            [Button.inline("⚖️ پلن مصرف منصفانه", data="PlanType_fair_usage")],
            [Button.inline("♾️ پلن نامحدود حجمی", data="PlanType_unlimited_volume")],
            [Button.inline("🔙 بازگشت", data="PlanAddSelectPanel")],
        ]
        await event.edit("نوع پلن را انتخاب کنید:", buttons=buttons)

    elif data.startswith("PlanType_"):
        plan_type = data.replace("PlanType_", "")  # "volume", "fair_usage", or "unlimited_volume"
        await set_data(user_id, "plan_type", plan_type)

        if plan_type == "volume" or plan_type == "unlimited_volume":
            buttons = [
                [
                    Button.inline("🔙 بازگشت به منوی پلن", data="BackToPlanMainMenu"),
                    Button.inline("🔙 بازگشت", data="BackToPlanType"),
                ],
            ]
            sent_msg = await event.edit(
                "📍 مقدار گیگ مورد نظر را وارد کنید (مثال: 0.5 برای نیم گیگابایت):", buttons=buttons
            )
            await set_data(user_id, "addPlan_volume_msg_id", str(sent_msg.id))
            await set_step(user_id, "addPlan_1")
        else:
            buttons = [
                [Button.inline("📅 ریست روزانه", data="ResetStrategy_day")],
                [Button.inline("📆 ریست هفتگی", data="ResetStrategy_week")],
                [Button.inline("🗓️ ریست ماهانه", data="ResetStrategy_month")],
                [Button.inline("📊 ریست سالانه", data="ResetStrategy_year")],
                [Button.inline("🔙 بازگشت", data="BackToPlanType")],
            ]
            await event.edit("استراتژی ریست حجم را انتخاب کنید:", buttons=buttons)

    elif data.startswith("ResetStrategy_"):
        reset_strategy = data.split("_")[1]  # "day", "week", "month", "year"
        await set_data(user_id, "reset_strategy", reset_strategy)

        buttons = [
            [
                Button.inline("🔙 بازگشت به منوی پلن", data="BackToPlanMainMenu"),
                Button.inline("🔙 بازگشت", data="BackToResetStrategy"),
            ],
        ]
        sent_msg = await event.edit(
            "📍 مقدار گیگ مورد نظر را وارد کنید (مثال: 0.5 برای نیم گیگابایت):", buttons=buttons
        )
        await set_data(user_id, "addPlan_volume_msg_id", str(sent_msg.id))
        await set_step(user_id, "addPlan_1")

    elif data == "BackToPlanType":
        panel_code = await get_data(user_id, "selected_panel")
        # Reset step to allow selecting plan type again - important for step validation
        await set_step(user_id, "panel")
        # Clear plan creation steps to prevent confusion
        await delete_data(user_id, "addPlanHajm")
        await delete_data(user_id, "addPlanTime")
        await delete_data(user_id, "addPlanPrice")
        await delete_data(user_id, "plan_type")
        await delete_data(user_id, "reset_strategy")
        await delete_data(user_id, "addPlan_volume_msg_id")
        await delete_data(user_id, "addPlan_time_msg_id")
        await delete_data(user_id, "addPlan_price_msg_id")
        await delete_data(user_id, "addPlan_ip_limit_msg_id")

        if panel_code:
            buttons = [
                [Button.inline("📊 پلن حجمی", data="PlanType_volume")],
                [Button.inline("⚖️ پلن مصرف منصفانه", data="PlanType_fair_usage")],
                [Button.inline("♾️ پلن نامحدود حجمی", data="PlanType_unlimited_volume")],
                [Button.inline("🔙 بازگشت", data=f"AddPlans_{panel_code}")],
            ]
            await event.edit("نوع پلن را انتخاب کنید:", buttons=buttons)
        else:
            # If panel_code not found, go back to panel selection
            await event.edit(
                "لطفاً پنل مورد نظر خود را انتخاب کنید:",
                buttons=[[Button.inline("🔙 بازگشت", data="PlanAddSelectPanel")]],
            )

    elif data == "BackToResetStrategy":
        buttons = [
            [Button.inline("📅 ریست روزانه", data="ResetStrategy_day")],
            [Button.inline("📆 ریست هفتگی", data="ResetStrategy_week")],
            [Button.inline("🗓️ ریست ماهانه", data="ResetStrategy_month")],
            [Button.inline("📊 ریست سالانه", data="ResetStrategy_year")],
            [Button.inline("🔙 بازگشت", data="BackToPlanType")],
        ]
        await event.edit("استراتژی ریست حجم را انتخاب کنید:", buttons=buttons)

    elif data.startswith("UpdateAllPlans_"):
        panel_code = int(data.split("_")[1])
        plans = await PlanManager().get_all_plans(panel_code=panel_code)
        # Sort by time (duration) first, then by storage
        plans = sorted(plans, key=lambda p: (p.duration, p.storage))

        if not plans:
            await event.answer("هیچ پلنی موجود نیست!", alert=True)
            return

        message = "✏️ **برای اپدیت گروهی پلن‌ها، این پیام را ویرایش کنید و دوباره ارسال کنید:**\n\n"
        message += "📝 **فرمت:**\n"
        message += "`id=1, price=123, data_limit=10, time=30, ip_limit=1`\n\n"
        message += "**پلن‌های فعلی (ویرایش کنید و ارسال کنید):**\n\n"
        message += "```\n"

        for plan in plans:
            message += f"id={plan.id}, price={int(plan.price)}, data_limit={int(plan.storage)}, time={plan.duration}, ip_limit={plan.ip_limit}\n"

        message += "```"

        # Store message ID and panel_code for later use
        buttons = [
            [Button.inline("❌ لغو عملیات", data="CancelBulkUpdatePlans")],
        ]
        sent_message = await event.edit(message, parse_mode="markdown", buttons=buttons)
        await set_data(user_id, "bulk_update_plans_message_id", str(sent_message.id))
        await set_data(user_id, "bulk_update_plans_panel_code", str(panel_code))
        await set_step(user_id, "bulk_update_plans")

    elif data.startswith("ListPlans_"):
        panel_code = int(data.split("_")[1])
        await set_data(user_id, "selected_panel_manage", str(panel_code))
        await set_data(user_id, "plan_list_page", "1")
        await display_plans(user_id, panel_code, current_page=1, edit_message=True, original_event=event)

    elif data.startswith("GetPlansPriceList_"):
        panel_code = int(data.split("_")[1])
        plans = await PlanManager().get_all_plans(panel_code=panel_code)

        if not plans:
            await event.answer("هیچ پلنی موجود نیست!", alert=True)
            return

        buttons = [
            [Button.inline("💰 بر اساس قیمت", data=f"SortPlansByPrice_{panel_code}")],
            [Button.inline("⏰ بر اساس زمان", data=f"SortPlansByTime_{panel_code}")],
            [Button.inline("💾 بر اساس حجم", data=f"SortPlansByVolume_{panel_code}")],
            [Button.inline("🔙 بازگشت", data=f"ManagePlans_{panel_code}")],
        ]
        await event.edit("📊 لیست قیمت‌ها را بر اساس چه معیاری مرتب کنم؟", buttons=buttons)

    elif data.startswith("SortPlansByPrice_"):
        panel_code = int(data.split("_")[1])
        plans = await PlanManager().get_all_plans(panel_code=panel_code)
        plans = sorted(plans, key=lambda p: p.price)

        message = "📊 **لیست قیمت‌ها (مرتب شده بر اساس قیمت)**\n\n"
        for plan in plans:
            ip_limit_text = "نامحدود" if plan.ip_limit == 0 else f"{plan.ip_limit} کاربر"
            message += f"💾 {plan.storage} گیگابایت - ⏰ {plan.duration} روز - 💰 {int(plan.price):,} تومان - 👥 محدودیت کاربر: {ip_limit_text}\n"

        buttons = [
            [Button.inline("🔙 بازگشت", data=f"GetPlansPriceList_{panel_code}")],
        ]
        await event.edit(message, parse_mode="markdown", buttons=buttons)

    elif data.startswith("SortPlansByTime_"):
        panel_code = int(data.split("_")[1])
        plans = await PlanManager().get_all_plans(panel_code=panel_code)
        plans = sorted(plans, key=lambda p: p.duration)

        message = "📊 **لیست قیمت‌ها (مرتب شده بر اساس زمان)**\n\n"
        for plan in plans:
            ip_limit_text = "نامحدود" if plan.ip_limit == 0 else f"{plan.ip_limit} کاربر"
            message += f"💾 {plan.storage} گیگابایت - ⏰ {plan.duration} روز - 💰 {int(plan.price):,} تومان - 👥 محدودیت کاربر: {ip_limit_text}\n"

        buttons = [
            [Button.inline("🔙 بازگشت", data=f"GetPlansPriceList_{panel_code}")],
        ]
        await event.edit(message, parse_mode="markdown", buttons=buttons)

    elif data.startswith("SortPlansByVolume_"):
        panel_code = int(data.split("_")[1])
        plans = await PlanManager().get_all_plans(panel_code=panel_code)
        plans = sorted(plans, key=lambda p: p.storage)

        message = "📊 **لیست قیمت‌ها (مرتب شده بر اساس حجم)**\n\n"
        for plan in plans:
            ip_limit_text = "نامحدود" if plan.ip_limit == 0 else f"{plan.ip_limit} کاربر"
            message += f"💾 {plan.storage} گیگابایت - ⏰ {plan.duration} روز - 💰 {int(plan.price):,} تومان - 👥 محدودیت کاربر: {ip_limit_text}\n"

        buttons = [
            [Button.inline("🔙 بازگشت", data=f"GetPlansPriceList_{panel_code}")],
        ]
        await event.edit(message, parse_mode="markdown", buttons=buttons)

    elif data == "DataCancelPlans":
        # Delete the current message and clean up
        with contextlib.suppress(Exception):
            await Kenzo.delete_messages(user_id, [event.original_update.msg_id])
        await clear_user(user_id)
        await set_step(user_id, "panel")

    elif data == "CancelBulkUpdatePlans":
        # Get panel_code from steps before deleting
        panel_code = await get_data(user_id, "bulk_update_plans_panel_code")
        await clear_user(user_id)
        await set_step(user_id, "panel")
        await event.answer("✅ عملیات اپدیت گروهی لغو شد", alert=True)

        if panel_code:
            buttons = [
                [Button.inline("✏️ اپدیت همه پلن‌ها با تکست", data=f"UpdateAllPlans_{panel_code}")],
                [Button.inline("📄 لیست پلن‌ها (صفحه‌بندی)", data=f"ListPlans_{panel_code}")],
                [Button.inline("🔙 بازگشت", data="PlanManageSelectPanel")],
            ]
            await event.edit("✅ عملیات لغو شد. لطفاً یکی از گزینه‌های زیر را انتخاب کنید:", buttons=buttons)
        else:
            await event.edit("✅ عملیات لغو شد")

    elif data == "BackToVolumeInput":
        # Go back to volume input - reset step
        await set_step(user_id, "addPlan_1")
        # Clear time, price, and ip_limit steps
        await delete_data(user_id, "addPlanTime")
        await delete_data(user_id, "addPlanPrice")
        buttons = [
            [
                Button.inline("🔙 بازگشت به منوی پلن", data="BackToPlanMainMenu"),
                Button.inline("🔙 بازگشت", data="BackToPlanType"),
            ],
        ]
        await event.edit("📍 مقدار گیگ مورد نظر را وارد کنید (مثال: 0.5 برای نیم گیگابایت):", buttons=buttons)

    elif data == "BackToTimeInput":
        # Go back to time input - reset step
        await set_step(user_id, "addPlan_2")
        # Clear price and ip_limit steps
        await delete_data(user_id, "addPlanPrice")
        # Get previous data (volume)
        hajm = await get_data(user_id, "addPlanHajm")
        hajm_text = f"{float(hajm)} گیگابایت" if hajm else "تعیین نشده"

        # Get the message ID that was stored when we sent the time input message
        time_msg_id = await get_data(user_id, "addPlan_time_msg_id")
        buttons = [
            [
                Button.inline("🔙 بازگشت به منوی پلن", data="BackToPlanMainMenu"),
                Button.inline("🔙 بازگشت", data="BackToVolumeInput"),
            ],
        ]
        message_text = f"💾 **حجم:** {hajm_text}\n\n"
        message_text += "📅 تعداد روز رو به عدد ( 123) وارد کنید:"

        if time_msg_id:
            try:
                await Kenzo.edit_message(
                    user_id, int(time_msg_id), message_text, buttons=buttons, parse_mode="markdown"
                )
            except Exception:
                # If edit fails, send new message
                sent_msg = await Kenzo.send_message(user_id, message_text, buttons=buttons, parse_mode="markdown")
                await set_data(user_id, "addPlan_time_msg_id", str(sent_msg.id))
        else:
            sent_msg = await Kenzo.send_message(user_id, message_text, buttons=buttons, parse_mode="markdown")
            await set_data(user_id, "addPlan_time_msg_id", str(sent_msg.id))

    elif data == "BackToPriceInput":
        # Go back to price input - reset step
        await set_step(user_id, "addPlan_3")
        # Clear ip_limit step
        # Get previous data (volume and time)
        hajm = await get_data(user_id, "addPlanHajm")
        time_days = await get_data(user_id, "addPlanTime")
        hajm_text = f"{float(hajm)} گیگابایت" if hajm else "تعیین نشده"
        time_text = f"{int(time_days)} روز" if time_days else "تعیین نشده"

        # Get the message ID that was stored when we sent the price input message
        price_msg_id = await get_data(user_id, "addPlan_price_msg_id")
        buttons = [
            [
                Button.inline("🔙 بازگشت به منوی پلن", data="BackToPlanMainMenu"),
                Button.inline("🔙 بازگشت", data="BackToTimeInput"),
            ],
        ]
        message_text = f"💾 **حجم:** {hajm_text}\n"
        message_text += f"📅 **زمان:** {time_text}\n\n"
        message_text += "💰 قیمت پلن رو ارسال کنید\nمثال» 10.000"

        if price_msg_id:
            try:
                await Kenzo.edit_message(
                    user_id, int(price_msg_id), message_text, buttons=buttons, parse_mode="markdown"
                )
            except Exception:
                # If edit fails, send new message
                sent_msg = await Kenzo.send_message(user_id, message_text, buttons=buttons, parse_mode="markdown")
                await set_data(user_id, "addPlan_price_msg_id", str(sent_msg.id))
        else:
            sent_msg = await Kenzo.send_message(user_id, message_text, buttons=buttons, parse_mode="markdown")
            await set_data(user_id, "addPlan_price_msg_id", str(sent_msg.id))

    elif data == "BackToIPLimitInput":
        # Go back to IP limit input - reset step
        await set_step(user_id, "addPlan_4")
        # Get previous data (volume, time, price)
        hajm = await get_data(user_id, "addPlanHajm")
        time_days = await get_data(user_id, "addPlanTime")
        price = await get_data(user_id, "addPlanPrice")
        hajm_text = f"{float(hajm)} گیگابایت" if hajm else "تعیین نشده"
        time_text = f"{int(time_days)} روز" if time_days else "تعیین نشده"
        price_text = f"{int(price):,} تومان" if price else "تعیین نشده"

        # Get the message ID that was stored when we sent the IP limit input message
        ip_limit_msg_id = await get_data(user_id, "addPlan_ip_limit_msg_id")
        buttons = [
            [
                Button.inline("🔙 بازگشت به منوی پلن", data="BackToPlanMainMenu"),
                Button.inline("🔙 بازگشت", data="BackToPriceInput"),
            ],
        ]
        message_text = f"💾 **حجم:** {hajm_text}\n"
        message_text += f"📅 **زمان:** {time_text}\n"
        message_text += f"💰 **قیمت:** {price_text}\n\n"
        message_text += "🔌 محدودیت کاربر (IP Limit) را وارد کنید:\n(0 برای نامحدود، یا عدد برای تعداد کاربر)"

        if ip_limit_msg_id:
            try:
                await Kenzo.edit_message(
                    user_id,
                    int(ip_limit_msg_id),
                    message_text,
                    buttons=buttons,
                    parse_mode="markdown",
                )
            except Exception:
                # If edit fails, send new message
                sent_msg = await Kenzo.send_message(
                    user_id,
                    message_text,
                    buttons=buttons,
                    parse_mode="markdown",
                )
                await set_data(user_id, "addPlan_ip_limit_msg_id", str(sent_msg.id))
        else:
            sent_msg = await Kenzo.send_message(
                user_id,
                message_text,
                buttons=buttons,
                parse_mode="markdown",
            )
            await set_data(user_id, "addPlan_ip_limit_msg_id", str(sent_msg.id))


def plans_callback_filter(event: events.CallbackQuery.Event) -> bool:
    return event.sender_id in ADMIN_ID


def register(client):
    client.add_event_handler(
        inline_callback,
        events.CallbackQuery(func=plans_callback_filter),
    )
