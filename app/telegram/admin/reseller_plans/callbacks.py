"""Callback handlers for admin reseller plans."""

from telethon import Button, events

from app import Kenzo
from app.db.crud.panels import PanelsManager
from app.db.crud.reseller_plans import ResellerPlanManager
from app.services.billing.reseller_pricing import pricing_mode_label
from app.services.panels.admins import fetch_panel_roles
from app.services.reseller.import_existing import import_existing_reseller_admin
from app.telegram.admin.reseller_plans import states
from app.telegram.admin.reseller_plans.service import (
    format_reseller_import_plan_button,
    format_reseller_plan_detail,
    format_reseller_plan_list_label,
    plan_manage_buttons,
    reseller_plan_display_buttons,
    reseller_plan_display_config_text,
    reseller_plan_main_menu_buttons,
)
from app.telegram.shared.utils.maintenance import bot_is_offline
from app.telegram.state import clear_user, get_data, set_data, set_step
from app.utils.formatting.conversions import as_int, gigabytes_to_bytes
from config import ADMIN_ID


def is_number(msg: str) -> bool:
    try:
        float(msg.replace(",", ""))
        return True
    except ValueError:
        return False


async def _show_import_plan_picker(_event, user_id: int, panel_code: int) -> None:
    panel = await PanelsManager().get_panel_by_code(code=panel_code)
    plans = await ResellerPlanManager().get_all_plans(panel_code=panel_code)
    if not plans:
        await Kenzo.send_message(user_id, "پلنی برای این پنل وجود ندارد.")
        return
    panel_name = panel.name if panel else str(panel_code)
    buttons = [[Button.inline(format_reseller_import_plan_button(p), data=f"ResellerImportPlan_{p.id}")] for p in plans]
    buttons.append([Button.inline("🔙 بازگشت", data=f"ResellerImportPanel_{panel_code}")])
    await Kenzo.send_message(
        user_id,
        f"**📋 انتخاب پلن صورتحساب — {panel_name}**\n\n"
        "این پلن فقط برای مدیریت و صورتحساب داخل ربات است "
        "(ثابت / مصرفی / …) و محدودیت‌های فعلی پنل را تغییر نمی‌دهد.",
        buttons=buttons,
        parse_mode="markdown",
    )


@bot_is_offline
async def reseller_plan_callbacks(event: events.CallbackQuery.Event):
    if not event.is_private or event.sender_id not in ADMIN_ID:
        return
    data = event.data.decode("utf-8")
    user_id = event.sender_id

    if data == "ResellerPlanMainMenu":
        await event.edit("منوی پلن‌های نمایندگی:", buttons=reseller_plan_main_menu_buttons())
        return

    if data == "ResellerPlanCancel":
        await clear_user(user_id)
        await set_step(user_id, "panel")
        await event.delete()
        return

    if data == "ResellerImportPanel":
        panels = await PanelsManager().get_all_panels()
        if not panels:
            await event.answer("پنلی وجود ندارد.", alert=True)
            return
        buttons = [[Button.inline(p.name, data=f"ResellerImportPanel_{p.code}")] for p in panels]
        buttons.append([Button.inline("🔙 بازگشت", data="ResellerPlanMainMenu")])
        await event.edit(
            "➕ افزودن ادمین موجود\n\nادمینی که از قبل در پنل ساخته شده را به ربات وصل می‌کند.\nپنل را انتخاب کنید:",
            buttons=buttons,
        )
        return

    if data.startswith("ResellerImportPanel_"):
        panel_code = as_int(data.split("_")[1])
        if panel_code is None:
            await event.answer("پنل نامعتبر است.", alert=True)
            return
        panel = await PanelsManager().get_panel_by_code(code=panel_code)
        if not panel:
            await event.answer("پنل یافت نشد.", alert=True)
            return
        await set_data(user_id, "reseller_import_panel_code", str(panel_code))
        await set_step(user_id, "reseller_import_username")
        await event.edit(
            f"➕ افزودن ادمین موجود — {panel.name}\n\n"
            "نام کاربری ادمینی که داخل پنل ساخته‌اید را ارسال کنید.\n"
            "مثال: agency01",
            buttons=[[Button.inline("🔙 بازگشت", data="ResellerImportPanel")]],
        )
        return

    if data.startswith("ResellerImportPlan_"):
        plan_id = as_int(data.split("_")[1])
        if plan_id is None:
            await event.answer("پلن نامعتبر است.", alert=True)
            return
        plan = await ResellerPlanManager().get_plan(plan_id)
        if not plan:
            await event.answer("پلن یافت نشد.", alert=True)
            return
        panel_code = as_int(await get_data(user_id, "reseller_import_panel_code"))
        username = await get_data(user_id, "reseller_import_username")
        telegram_id = as_int(await get_data(user_id, "reseller_import_telegram_id"))
        if panel_code is None or not username or telegram_id is None:
            await event.answer("اطلاعات ویزارد ناقص است. دوباره شروع کنید.", alert=True)
            return
        if int(plan.panel_code) != int(panel_code):
            await event.answer("پلن متعلق به این پنل نیست.", alert=True)
            return
        await set_data(user_id, "reseller_import_plan_id", str(plan_id))
        await event.edit(
            f"**⚠️ تایید افزودن ادمین موجود**\n\n"
            f"**👤 نام کاربری:** `{username}`\n"
            f"**🆔 تلگرام:** `{telegram_id}`\n"
            f"**📋 پلن:** #{plan.id} — {pricing_mode_label(plan.pricing_mode)}\n\n"
            "• رمز ادمین در پنل عوض می‌شود (رمز فعلی از پنل قابل خواندن نیست)\n"
            "• نوت روی آیدی تلگرام تنظیم می‌شود\n"
            "• محدودیت‌های فعلی پنل حفظ می‌مانند\n"
            "• به کاربر پیام فعال‌سازی با رمز جدید ارسال می‌شود",
            buttons=[
                [Button.inline("✅ تایید و افزودن", data="ResellerImportConfirm")],
                [Button.inline("🔙 بازگشت به لیست پلن", data=f"ResellerImportBackPlans_{panel_code}")],
            ],
            parse_mode="markdown",
        )
        return

    if data.startswith("ResellerImportBackPlans_"):
        panel_code = as_int(data.split("_")[1])
        if panel_code is None:
            await event.answer("پنل نامعتبر است.", alert=True)
            return
        await event.delete()
        await _show_import_plan_picker(event, user_id, panel_code)
        return

    if data == "ResellerImportConfirm":
        panel_code = as_int(await get_data(user_id, "reseller_import_panel_code"))
        username = await get_data(user_id, "reseller_import_username")
        telegram_id = as_int(await get_data(user_id, "reseller_import_telegram_id"))
        plan_id = as_int(await get_data(user_id, "reseller_import_plan_id"))
        if panel_code is None or not username or telegram_id is None or plan_id is None:
            await event.answer("اطلاعات ویزارد ناقص است.", alert=True)
            return
        _ok, message, _account, _password = await import_existing_reseller_admin(
            panel_code=panel_code,
            username=username,
            telegram_id=telegram_id,
            plan_id=plan_id,
            actor_id=user_id,
        )
        if _ok:
            await clear_user(user_id)
            await set_step(user_id, "panel")
        await event.edit(
            message,
            buttons=[[Button.inline("🔙 منوی پلن نمایندگی", data="ResellerPlanMainMenu")]],
            parse_mode="markdown",
        )
        return

    if data == "ResellerPlanAddPanel":
        panels = await PanelsManager().get_all_panels()
        if not panels:
            await event.answer("پنلی وجود ندارد.", alert=True)
            return
        buttons = [[Button.inline(p.name, data=f"ResellerPlanAdd_{p.code}")] for p in panels]
        buttons.append([Button.inline("🔙 بازگشت", data="ResellerPlanMainMenu")])
        await event.edit("پنل را انتخاب کنید:", buttons=buttons)
        return

    if data.startswith("ResellerPlanAdd_"):
        panel_code = int(data.split("_")[1])
        panel = await PanelsManager().get_panel_by_code(code=panel_code)
        if not panel:
            await event.answer("پنل یافت نشد.", alert=True)
            return
        roles = await fetch_panel_roles(panel)
        if not roles:
            await event.answer("نقشی از پنل دریافت نشد. دسترسی credential را بررسی کنید.", alert=True)
            return
        await set_data(user_id, "reseller_plan_panel", str(panel_code))
        page_size = 15
        page = 0
        filtered = [r for r in roles if not r.get("is_owner")] or list(roles)
        start = page * page_size
        end = start + page_size
        page_roles = filtered[start:end]
        buttons = [[Button.inline(f"{r['name']}", data=f"ResellerPlanRole_{r['id']}")] for r in page_roles]
        nav_buttons = []
        if page > 0:
            nav_buttons.append(Button.inline("◀️ قبلی", data=f"ResellerPlanRoles_{panel_code}:{page - 1}"))
        if end < len(filtered):
            nav_buttons.append(Button.inline("بعدی ▶️", data=f"ResellerPlanRoles_{panel_code}:{page + 1}"))
        if nav_buttons:
            buttons.append(nav_buttons)
        buttons.append([Button.inline("🔙 بازگشت", data="ResellerPlanAddPanel")])
        await event.edit("نقش (Role) نماینده را انتخاب کنید:", buttons=buttons)
        return

    if data.startswith("ResellerPlanRoles_"):
        payload = data.replace("ResellerPlanRoles_", "", 1)
        panel_code_raw, page_raw = payload.split(":", 1)
        panel_code = as_int(panel_code_raw)
        page = as_int(page_raw)
        if panel_code is None or page is None:
            await event.answer("صفحه نامعتبر است.", alert=True)
            return
        panel = await PanelsManager().get_panel_by_code(code=panel_code)
        if not panel:
            await event.answer("پنل یافت نشد.", alert=True)
            return
        roles = await fetch_panel_roles(panel)
        if not roles:
            await event.answer("نقشی از پنل دریافت نشد. دسترسی credential را بررسی کنید.", alert=True)
            return
        page_size = 15
        filtered = [r for r in roles if not r.get("is_owner")] or list(roles)
        if not filtered:
            await event.answer("نقشی برای نمایش وجود ندارد.", alert=True)
            return
        total_pages = (len(filtered) - 1) // page_size + 1
        page = max(0, min(page, total_pages - 1))
        start = page * page_size
        end = start + page_size
        page_roles = filtered[start:end]
        buttons = [[Button.inline(f"{r['name']}", data=f"ResellerPlanRole_{r['id']}")] for r in page_roles]
        nav_buttons = []
        if page > 0:
            nav_buttons.append(Button.inline("◀️ قبلی", data=f"ResellerPlanRoles_{panel_code}:{page - 1}"))
        if page < total_pages - 1:
            nav_buttons.append(Button.inline("بعدی ▶️", data=f"ResellerPlanRoles_{panel_code}:{page + 1}"))
        if nav_buttons:
            buttons.append(nav_buttons)
        buttons.append([Button.inline("🔙 بازگشت", data="ResellerPlanAddPanel")])
        await event.edit("نقش (Role) نماینده را انتخاب کنید:", buttons=buttons)
        return

    if data.startswith("ResellerPlanRole_"):
        role_id = as_int(data.replace("ResellerPlanRole_", "", 1))
        if role_id is None:
            await event.answer("نقش نامعتبر است.", alert=True)
            return
        role_name = str(role_id)
        await set_data(user_id, "reseller_plan_role_id", str(role_id))
        await set_data(user_id, "reseller_plan_role_name", role_name)
        mode_buttons = [
            [Button.inline(label, data=f"ResellerPlanMode_{key}")] for key, label in states.PRICING_MODE_LABELS.items()
        ]
        mode_buttons.append([Button.inline("🔙 بازگشت", data="ResellerPlanAddPanel")])
        await event.edit("نوع قیمت‌گذاری:", buttons=mode_buttons)
        return

    if data.startswith("ResellerPlanMode_"):
        mode = data.replace("ResellerPlanMode_", "", 1)
        await set_data(user_id, "reseller_plan_mode", mode)
        if mode == "fixed":
            await event.edit("قیمت ثابت (تومان) را ارسال کنید:")
            await set_step(user_id, "reseller_plan_add_price")
        elif mode == "usage":
            await event.edit("قیمت هر گیگ مصرف (تومان) را ارسال کنید:")
            await set_step(user_id, "reseller_plan_add_unit_price")
        return

    if data == "ResellerPlanManagePanel":
        panels = await PanelsManager().get_all_panels()
        buttons = [[Button.inline(p.name, data=f"ResellerPlanManage_{p.code}")] for p in panels]
        buttons.append([Button.inline("🔙 بازگشت", data="ResellerPlanMainMenu")])
        await event.edit("پنل:", buttons=buttons)
        return

    if data.startswith("ResellerPlanManage_"):
        panel_code = int(data.split("_")[1])
        panel = await PanelsManager().get_panel_by_code(code=panel_code)
        plans = await ResellerPlanManager().get_all_plans(panel_code=panel_code)
        if not plans:
            await event.answer("پلنی نیست.", alert=True)
            return
        panel_name = panel.name if panel else str(panel_code)
        buttons = [[Button.inline(format_reseller_plan_list_label(p), data=f"ResellerPlanView_{p.id}")] for p in plans]
        buttons.append([Button.inline("🔙 بازگشت", data="ResellerPlanManagePanel")])
        await event.edit(
            f"**📋 پلن‌های نمایندگی — {panel_name}**\n\nیک پلن را انتخاب کنید:",
            buttons=buttons,
            parse_mode="markdown",
        )
        return

    if data.startswith("ResellerPlanView_"):
        plan_id = int(data.split("_")[1])
        plan = await ResellerPlanManager().get_plan(plan_id)
        if not plan:
            await event.answer("یافت نشد.", alert=True)
            return
        await event.edit(
            await format_reseller_plan_detail(plan),
            buttons=plan_manage_buttons(plan_id, plan.panel_code),
            parse_mode="markdown",
        )
        return

    if data.startswith("ResellerPlanToggle_"):
        plan_id = int(data.split("_")[1])
        plan = await ResellerPlanManager().get_plan(plan_id)
        if plan:
            await ResellerPlanManager().update_plan(plan_id, enable=not plan.enable)
            plan = await ResellerPlanManager().get_plan(plan_id)
            await event.edit(
                await format_reseller_plan_detail(plan),
                buttons=plan_manage_buttons(plan_id, plan.panel_code),
                parse_mode="markdown",
            )
        return

    if data.startswith("ResellerPlanDelete_"):
        plan_id = int(data.split("_")[1])
        plan = await ResellerPlanManager().get_plan(plan_id)
        if not plan:
            await event.answer("یافت نشد.", alert=True)
            return
        ok, msg = await ResellerPlanManager().delete_plan(plan_id)
        if not ok:
            await event.answer(msg, alert=True)
            return
        await event.answer(msg, alert=True)
        await event.edit(
            "پلن حذف شد.",
            buttons=[[Button.inline("🔙 بازگشت", data=f"ResellerPlanManage_{plan.panel_code}")]],
        )
        return

    if data.startswith("ResellerPlanEditPrice_"):
        plan_id = int(data.split("_")[1])
        plan = await ResellerPlanManager().get_plan(plan_id)
        if not plan:
            await event.answer("یافت نشد.", alert=True)
            return
        await set_data(user_id, "reseller_edit_plan_id", str(plan_id))
        label = "قیمت ثابت" if plan.pricing_mode == "fixed" else "قیمت واحد"
        await event.edit(
            f"**✏️ تغییر {label} — پلن #{plan_id}**\n\nمبلغ جدید (تومان) را ارسال کنید:",
            buttons=[[Button.inline("🔙 بازگشت", data=f"ResellerPlanView_{plan_id}")]],
            parse_mode="markdown",
        )
        await set_step(user_id, "reseller_plan_edit_price")
        return

    if data.startswith("ResellerPlanDisplay_"):
        plan_id = int(data.split("_")[1])
        plan = await ResellerPlanManager().get_plan(plan_id)
        if not plan:
            await event.answer("یافت نشد.", alert=True)
            return
        await event.edit(
            reseller_plan_display_config_text(plan),
            buttons=reseller_plan_display_buttons(plan_id, plan.panel_code),
            parse_mode="markdown",
        )
        return

    if data.startswith("ResellerPlanBtnText_"):
        plan_id = int(data.split("_")[1])
        plan = await ResellerPlanManager().get_plan(plan_id)
        if not plan:
            await event.answer("یافت نشد.", alert=True)
            return
        from app.telegram.user.reseller.helpers import format_plan_button_text

        preview = format_plan_button_text(plan)
        await set_data(user_id, "reseller_edit_plan_id", str(plan_id))
        await set_step(user_id, "reseller_plan_edit_btn_text")
        await event.edit(
            f"**✏️ متن دکمه پلن #{plan_id}**\n\n"
            f"پیش‌نمایش فعلی: `{preview}`\n\n"
            "متن جدید را ارسال کنید یا `/skip` برای قالب خودکار:",
            buttons=[[Button.inline("🔙 بازگشت", data=f"ResellerPlanDisplay_{plan_id}")]],
            parse_mode="markdown",
        )
        return

    if data.startswith("ResellerPlanBtnColor_"):
        payload = data.replace("ResellerPlanBtnColor_", "", 1)
        plan_id_str, style_val = payload.split(":", 1)
        plan_id = int(plan_id_str)
        style = "" if style_val == "none" else style_val
        await ResellerPlanManager().update_plan(plan_id, button_style=style)
        plan = await ResellerPlanManager().get_plan(plan_id)
        if not plan:
            await event.answer("یافت نشد.", alert=True)
            return
        await event.answer("رنگ دکمه به‌روز شد.", alert=False)
        await event.edit(
            reseller_plan_display_config_text(plan),
            buttons=reseller_plan_display_buttons(plan_id, plan.panel_code),
            parse_mode="markdown",
        )
        return

    if data.startswith("ResellerPlanBtnIconClear_"):
        plan_id = int(data.split("_")[1])
        await ResellerPlanManager().update_plan(plan_id, button_icon=None)
        plan = await ResellerPlanManager().get_plan(plan_id)
        if not plan:
            await event.answer("یافت نشد.", alert=True)
            return
        await event.answer("آیکون حذف شد.", alert=False)
        await event.edit(
            reseller_plan_display_config_text(plan),
            buttons=reseller_plan_display_buttons(plan_id, plan.panel_code),
            parse_mode="markdown",
        )
        return

    if data.startswith("ResellerPlanBtnIcon_"):
        plan_id = int(data.split("_")[1])
        plan = await ResellerPlanManager().get_plan(plan_id)
        if not plan:
            await event.answer("یافت نشد.", alert=True)
            return
        await set_data(user_id, "reseller_edit_plan_id", str(plan_id))
        await set_step(user_id, "reseller_plan_edit_btn_icon")
        await event.edit(
            f"**🖼 آیکون پلن #{plan_id}**\n\nیک ایموجی پریمیوم ارسال کنید یا شناسه عددی آن را بفرستید:",
            buttons=[[Button.inline("🔙 بازگشت", data=f"ResellerPlanDisplay_{plan_id}")]],
            parse_mode="markdown",
        )
        return

    if data.startswith("ResellerPlanBtnReset_"):
        plan_id = int(data.split("_")[1])
        await ResellerPlanManager().update_plan(
            plan_id,
            display_button_text=None,
            button_style=None,
            button_icon=None,
        )
        plan = await ResellerPlanManager().get_plan(plan_id)
        if not plan:
            await event.answer("یافت نشد.", alert=True)
            return
        await event.answer("تنظیمات نمایش ریست شد.", alert=False)
        await event.edit(
            reseller_plan_display_config_text(plan),
            buttons=reseller_plan_display_buttons(plan_id, plan.panel_code),
            parse_mode="markdown",
        )
        return


async def _finalize_new_plan(event, user_id: int):
    panel_code = int(await get_data(user_id, "reseller_plan_panel"))
    role_id = int(await get_data(user_id, "reseller_plan_role_id"))
    role_name = await get_data(user_id, "reseller_plan_role_name")
    mode = await get_data(user_id, "reseller_plan_mode")
    price = float((await get_data(user_id, "reseller_plan_price")) or 0)
    unit_price = float((await get_data(user_id, "reseller_plan_unit_price")) or 0)
    data_limit_gb = float((await get_data(user_id, "reseller_plan_data_limit")) or 0)
    max_users = int((await get_data(user_id, "reseller_plan_max_users")) or 0)
    duration = int((await get_data(user_id, "reseller_plan_duration")) or 0)
    min_volume = float((await get_data(user_id, "reseller_plan_min_volume")) or 0)
    max_volume = float((await get_data(user_id, "reseller_plan_max_volume")) or 0)

    plan = await ResellerPlanManager().add_plan(
        panel_code=panel_code,
        pricing_mode=mode,
        price=price if mode == "fixed" else 0,
        unit_price=unit_price if mode != "fixed" else 0,
        min_volume=min_volume,
        max_volume=max_volume,
        volume_step=1,
        data_limit=int(gigabytes_to_bytes(data_limit_gb)) if data_limit_gb else 0,
        max_users=max_users,
        duration=duration,
        role_id=role_id,
        role_name=role_name,
        enable=True,
    )
    await clear_user(user_id)
    await set_step(user_id, "panel")
    if plan:
        await Kenzo.send_message(user_id, f"✅ پلن نمایندگی #{plan.id} ساخته شد.")
    else:
        await Kenzo.send_message(user_id, "❌ خطا در ساخت پلن.")


def register(client):
    client.add_event_handler(
        reseller_plan_callbacks,
        events.CallbackQuery(pattern=rb"^(ResellerPlan|ResellerImport)"),
    )
