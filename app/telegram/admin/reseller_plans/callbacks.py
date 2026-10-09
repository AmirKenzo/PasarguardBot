"""Callback handlers for admin reseller plans."""

from telethon import Button, events

from app import Kenzo
from app.db.crud.panels import PanelsManager
from app.db.crud.reseller_plans import ResellerPlanManager
from app.services.panels.admins import fetch_panel_roles
from app.services.reseller.import_existing import import_existing_reseller_admin
from app.services.reseller.plan_rules import CREATABLE_MODES, normalize_plan, rule_for, validate_plan
from app.telegram.admin.reseller_plans import states
from app.telegram.admin.reseller_plans.service import (
    edit_button_label,
    format_reseller_import_plan_button,
    format_reseller_plan_detail,
    format_reseller_plan_list_label,
    plan_manage_buttons,
    reseller_plan_display_buttons,
    reseller_plan_display_config_text,
    reseller_plan_main_menu_buttons,
)
from app.telegram.shared.reseller_plan_guides import (
    admin_mode_name,
    admin_type_guide,
    create_fields,
    editable_fields,
    field_label,
    field_prompt,
    format_field_value,
    load_guide_context,
    plan_values_summary,
)
from app.telegram.shared.utils.maintenance import bot_is_offline
from app.telegram.state import clear_user, delete_data_many, get_data, set_data, set_step
from app.utils.formatting.conversions import as_int, gigabytes_to_bytes
from config import ADMIN_ID

_ALL_VALUE_FIELDS = (
    "price",
    "unit_price",
    "data_limit",
    "max_users",
    "duration",
    "addon_day_price",
    "addon_gb_price",
    "addon_user_price",
)
_VALUE_KEYS = tuple(f"{states.VALUE_KEY_PREFIX}{name}" for name in _ALL_VALUE_FIELDS)
_WIZARD_KEYS = (states.ROLE_ID_KEY, states.ROLE_NAME_KEY, states.MODE_KEY, states.FIELD_KEY, *_VALUE_KEYS)


async def clear_plan_wizard(user_id: int) -> None:
    await delete_data_many(user_id, _WIZARD_KEYS)


def mode_picker_buttons() -> list:
    rows = [[Button.inline(label, data=f"ResellerPlanMode_{key}")] for key, label in states.PRICING_MODE_LABELS.items()]
    rows.append([Button.inline("🔙 بازگشت", data="ResellerPlanAddPanel")])
    return rows


MODE_PICKER_TEXT = (
    "**📋 نوع پلن نمایندگی را انتخاب کنید:**\n\n"
    "📦 **ثابت** — پیش‌پرداخت با حجم و مدت مشخص\n"
    "♾ **نامحدود (زمانی)** — پیش‌پرداخت با حجم نامحدود و مدت مشخص\n"
    "📊 **مصرفی (بر اساس حجم مصرف)** — کسر از کیف پول به‌ازای هر گیگ مصرف\n"
    "⏱ **ساعتی (بر اساس زمان فعال بودن)** — کسر از کیف پول به‌ازای هر ساعت فعال بودن\n\n"
    "بعد از انتخاب، راهنمای کامل همان نوع نمایش داده می‌شود."
)


async def wizard_values(user_id: int) -> dict:
    """Model values of the plan being created (``data_limit`` converted from GB to bytes)."""
    values: dict = {"pricing_mode": await get_data(user_id, states.MODE_KEY)}
    for name in _ALL_VALUE_FIELDS:
        raw = await get_data(user_id, f"{states.VALUE_KEY_PREFIX}{name}")
        if raw is None:
            continue
        number = float(raw)
        if name == "data_limit":
            values[name] = int(gigabytes_to_bytes(number)) if number > 0 else 0
        elif name in ("max_users", "duration"):
            values[name] = int(number)
        else:
            values[name] = number
    return values


def wizard_cancel_row() -> list:
    return [Button.inline("❌ انصراف", data="ResellerPlanCancel")]


async def ask_create_field(user_id: int, mode: str, field: str, *, event=None, intro: str | None = None) -> None:
    """Ask one plan field; edits the callback message when ``event`` is given."""
    await set_data(user_id, states.FIELD_KEY, field)
    await set_step(user_id, states.STEP_ADD_FIELD)
    fields = create_fields(mode)
    text = f"**✏️ مرحله {fields.index(field) + 1} از {len(fields)}**\n{field_prompt(field, mode)}"
    if intro:
        text = f"{intro}\n\n━━━━━━━━━━━━\n{text}"
    role_id = await get_data(user_id, states.ROLE_ID_KEY)
    buttons = [[Button.inline("🔙 تغییر نوع پلن", data=f"ResellerPlanRole_{role_id}")], wizard_cancel_row()]
    if event is not None:
        await event.edit(text, buttons=buttons, parse_mode="markdown")
    else:
        await Kenzo.send_message(user_id, text, buttons=buttons, parse_mode="markdown")


def _complete_values(values: dict) -> dict:
    """Fill fields that were not asked (unused by the type or skipped) with 0, then clear unused ones."""
    base = dict.fromkeys(_ALL_VALUE_FIELDS, 0)
    out = normalize_plan({**base, **values})
    if int(out.get("max_users") or 0) <= 0:
        out["addon_user_price"] = 0
    return out


async def send_create_review(user_id: int) -> None:
    """Show the plan before saving, or the rule error that blocks it (same rules as the web panel)."""
    values = _complete_values(await wizard_values(user_id))
    mode = values.get("pricing_mode")
    await set_step(user_id, "panel")
    summary = plan_values_summary(values)
    error = validate_plan(values)
    if error:
        await Kenzo.send_message(
            user_id,
            f"**❌ پلن قابل ساخت نیست**\n\n{summary}\n\n⚠️ {error}",
            buttons=[[Button.inline("🔁 وارد کردن دوباره", data=f"ResellerPlanMode_{mode}")], wizard_cancel_row()],
            parse_mode="markdown",
        )
        return
    await Kenzo.send_message(
        user_id,
        f"**🧾 بررسی پلن جدید**\n\n{summary}\n\nاگر درست است، ساخت پلن را تأیید کنید:",
        buttons=[
            [Button.inline("✅ ساخت پلن", data="ResellerPlanCreateConfirm")],
            [Button.inline("🔁 وارد کردن دوباره", data=f"ResellerPlanMode_{mode}")],
            wizard_cancel_row(),
        ],
        parse_mode="markdown",
    )


def plan_model_values(plan) -> dict:
    values: dict = {"pricing_mode": plan.pricing_mode}
    for name in (*_ALL_VALUE_FIELDS, "min_volume", "max_volume"):
        values[name] = getattr(plan, name, 0) or 0
    return values


def _without_other_errors(values: dict, field: str) -> dict:
    """``values`` with every field except ``field`` replaced by a valid value where it breaks a rule."""
    rule = rule_for(values.get("pricing_mode"))
    out = dict(values)
    for name in _ALL_VALUE_FIELDS:
        if name != field and float(out.get(name) or 0) < 0:
            out[name] = 0
    required = [rule.price_field]
    if rule.volume == "required":
        required.append("data_limit")
    if rule.duration == "required":
        required.append("duration")
    for name in required:
        if name != field and float(out.get(name) or 0) <= 0:
            out[name] = 1
    if field not in ("min_volume", "max_volume") and float(out.get("max_volume") or 0) < float(
        out.get("min_volume") or 0
    ):
        out["max_volume"] = 0
    return out


def edit_error(plan, field: str, value) -> str | None:
    """Rule error caused by setting ``field`` to ``value``, judged on that field alone.

    Other fields that already break a rule (an old plan created before the rules) are treated as
    valid here, so the admin can fix such a plan one field at a time in any order.
    """
    values = _without_other_errors({**plan_model_values(plan), field: value}, field)
    return validate_plan(values, existing_mode=plan.pricing_mode)


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
        await clear_plan_wizard(user_id)
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
            f"**📋 پلن:** #{plan.id} — {admin_mode_name(plan.pricing_mode)}\n\n"
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
        await clear_plan_wizard(user_id)
        await set_step(user_id, "panel")
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
        panel_code = as_int(await get_data(user_id, states.PANEL_KEY))
        if panel_code is None:
            await event.answer("پنل انتخاب نشده است. دوباره از منو شروع کنید.", alert=True)
            return
        role_name = await get_data(user_id, states.ROLE_NAME_KEY)
        if not role_name or await get_data(user_id, states.ROLE_ID_KEY) != str(role_id):
            role_name = str(role_id)
            panel = await PanelsManager().get_panel_by_code(code=panel_code)
            if panel:
                roles = await fetch_panel_roles(panel)
                role_name = next((str(r["name"]) for r in roles if int(r["id"]) == role_id), role_name)
        await set_data(user_id, states.ROLE_ID_KEY, str(role_id))
        await set_data(user_id, states.ROLE_NAME_KEY, role_name)
        await set_step(user_id, "panel")
        await event.edit(MODE_PICKER_TEXT, buttons=mode_picker_buttons(), parse_mode="markdown")
        return

    if data.startswith("ResellerPlanMode_"):
        mode = data.replace("ResellerPlanMode_", "", 1)
        if mode not in CREATABLE_MODES:
            await event.answer("پلن جدید فقط از نوع ثابت، نامحدود، مصرفی یا ساعتی ساخته می‌شود.", alert=True)
            return
        if not await get_data(user_id, states.PANEL_KEY) or not await get_data(user_id, states.ROLE_ID_KEY):
            await event.answer("اطلاعات ویزارد ناقص است. دوباره از منو شروع کنید.", alert=True)
            return
        await delete_data_many(user_id, (states.FIELD_KEY, *_VALUE_KEYS))
        await set_data(user_id, states.MODE_KEY, mode)
        guide = admin_type_guide(mode, await load_guide_context())
        await ask_create_field(user_id, mode, create_fields(mode)[0], event=event, intro=guide)
        return

    if data == "ResellerPlanCreateConfirm":
        await _finalize_new_plan(event, user_id)
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
        await set_step(user_id, "panel")
        await event.edit(
            await format_reseller_plan_detail(plan),
            buttons=plan_manage_buttons(plan),
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
                buttons=plan_manage_buttons(plan),
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

    if data.startswith(("ResellerPlanEditPrice_", "ResellerPlanEditField_")):
        payload = data.split("_", 1)[1]
        plan_id_raw, _, field = payload.partition(":")
        plan = await ResellerPlanManager().get_plan(as_int(plan_id_raw))
        if not plan:
            await event.answer("یافت نشد.", alert=True)
            return
        field = field or rule_for(plan.pricing_mode).price_field
        if field not in editable_fields(plan.pricing_mode, plan):
            await event.answer("این مقدار برای این نوع پلن قابل ویرایش نیست.", alert=True)
            return
        await set_data(user_id, states.EDIT_PLAN_KEY, str(plan.id))
        await set_data(user_id, states.EDIT_FIELD_KEY, field)
        await set_step(user_id, states.STEP_EDIT_FIELD)
        await event.edit(
            f"**✏️ تغییر {edit_button_label(field, plan.pricing_mode)} — پلن #{plan.id}**\n\n"
            f"مقدار فعلی: {format_field_value(field, getattr(plan, field, 0))}\n\n"
            f"{field_prompt(field, plan.pricing_mode)}",
            buttons=[[Button.inline("🔙 بازگشت", data=f"ResellerPlanView_{plan.id}")]],
            parse_mode="markdown",
        )
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


async def _finalize_new_plan(event, user_id: int) -> None:
    panel_code = as_int(await get_data(user_id, states.PANEL_KEY))
    role_id = as_int(await get_data(user_id, states.ROLE_ID_KEY))
    role_name = await get_data(user_id, states.ROLE_NAME_KEY)
    raw_values = await wizard_values(user_id)
    mode = raw_values.get("pricing_mode")
    if panel_code is None or role_id is None or mode not in CREATABLE_MODES:
        await event.answer("اطلاعات ویزارد ناقص است. دوباره از منو شروع کنید.", alert=True)
        return
    missing = [name for name in create_fields(mode) if name not in raw_values and name != "addon_user_price"]
    if missing:
        await event.answer(f"{field_label(missing[0], mode)} وارد نشده است.", alert=True)
        return
    values = _complete_values(raw_values)
    error = validate_plan(values)
    if error:
        await event.answer(error, alert=True)
        return

    plan = await ResellerPlanManager().add_plan(
        panel_code=panel_code,
        min_volume=0,
        max_volume=0,
        volume_step=1,
        role_id=role_id,
        role_name=role_name or str(role_id),
        enable=True,
        **values,
    )
    await clear_plan_wizard(user_id)
    await set_step(user_id, "panel")
    if not plan:
        await event.edit(
            "❌ خطا در ساخت پلن.", buttons=[[Button.inline("🔙 منوی پلن نمایندگی", data="ResellerPlanMainMenu")]]
        )
        return
    await event.edit(
        f"✅ پلن نمایندگی #{plan.id} ساخته شد.\n\n" + await format_reseller_plan_detail(plan),
        buttons=plan_manage_buttons(plan),
        parse_mode="markdown",
    )


def register(client):
    client.add_event_handler(
        reseller_plan_callbacks,
        events.CallbackQuery(pattern=rb"^(ResellerPlan|ResellerImport)"),
    )
