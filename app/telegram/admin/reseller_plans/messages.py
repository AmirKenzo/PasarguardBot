"""Message handlers for admin reseller plans."""

import contextlib

from telethon import events
from telethon.tl.custom import Message

from app import Kenzo
from app.db.crud.panels import PanelsManager
from app.db.crud.reseller_accounts import ResellerAccountCRUD
from app.db.crud.reseller_plans import ResellerPlanManager
from app.db.crud.user import UserCRUD
from app.services.panels.admins import find_admin_by_username
from app.services.reseller.import_existing import format_panel_admin_preview
from app.services.reseller.plan_changes import notify_plan_rate_change
from app.services.reseller.plan_rules import validate_plan
from app.telegram.admin.reseller_plans import states
from app.telegram.admin.reseller_plans.callbacks import (
    _show_import_plan_picker,
    ask_create_field,
    edit_error,
    plan_model_values,
    send_create_review,
)
from app.telegram.admin.reseller_plans.service import (
    format_reseller_plan_detail,
    plan_manage_buttons,
    reseller_plan_display_buttons,
    reseller_plan_display_config_text,
    reseller_plan_main_menu_buttons,
)
from app.telegram.keyboards.common import extract_custom_emoji_document_id
from app.telegram.shared.reseller_plan_guides import (
    create_fields,
    editable_fields,
    field_prompt,
    next_create_field,
    parse_plan_field,
)
from app.telegram.state import get_data, get_step, set_data, set_step
from app.utils.formatting.conversions import as_int, gigabytes_to_bytes
from config import ADMIN_ID


async def _show_plan_after_edit(event: Message, plan_id: int) -> None:
    plan = await ResellerPlanManager().get_plan(plan_id)
    if not plan:
        await event.respond("پلن یافت نشد.")
        return
    await Kenzo.send_message(
        event.sender_id,
        await format_reseller_plan_detail(plan),
        buttons=plan_manage_buttons(plan),
        parse_mode="markdown",
    )


async def _process_add_field(event: Message, user_id: int, msg: str) -> None:
    mode = await get_data(user_id, states.MODE_KEY)
    field = await get_data(user_id, states.FIELD_KEY)
    if not mode or not field or field not in create_fields(mode):
        await set_step(user_id, "panel")
        await event.respond("نشست ساخت پلن منقضی شده است. دوباره از منوی پلن نمایندگی شروع کنید.")
        return
    value, error = parse_plan_field(field, mode, msg)
    if error:
        await event.respond(f"❌ {error}\n\n{field_prompt(field, mode)}", parse_mode="markdown")
        return
    await set_data(user_id, f"{states.VALUE_KEY_PREFIX}{field}", str(value))
    with contextlib.suppress(Exception):
        await event.delete()
    entered = {field: value}
    if field != "max_users":
        raw_users = await get_data(user_id, f"{states.VALUE_KEY_PREFIX}max_users")
        if raw_users is not None:
            entered["max_users"] = int(float(raw_users))
    next_field = next_create_field(mode, field, entered)
    if next_field:
        await ask_create_field(user_id, mode, next_field)
        return
    await send_create_review(user_id)


async def _process_edit_field(event: Message, user_id: int, msg: str) -> None:
    plan_id = as_int(await get_data(user_id, states.EDIT_PLAN_KEY))
    field = await get_data(user_id, states.EDIT_FIELD_KEY)
    plan = await ResellerPlanManager().get_plan(plan_id) if plan_id is not None else None
    if not plan or not field or field not in editable_fields(plan.pricing_mode, plan):
        await set_step(user_id, "panel")
        await event.respond("نشست ویرایش منقضی شده است. دوباره پلن را باز کنید.")
        return
    value, error = parse_plan_field(field, plan.pricing_mode, msg)
    if error:
        await event.respond(f"❌ {error}\n\n{field_prompt(field, plan.pricing_mode)}", parse_mode="markdown")
        return
    if field == "data_limit":
        stored = int(gigabytes_to_bytes(value)) if value else 0
    elif field in ("max_users", "duration"):
        stored = int(value)
    else:
        stored = float(value)
    rule_error = edit_error(plan, field, stored)
    if rule_error:
        await event.respond(f"❌ {rule_error}\n\n{field_prompt(field, plan.pricing_mode)}", parse_mode="markdown")
        return
    old_rate = float(plan.unit_price or 0)
    if not await ResellerPlanManager().update_plan(plan.id, **{field: stored}):
        await event.respond("❌ ذخیره تغییر ناموفق بود. دوباره تلاش کنید.")
        return
    if field == "unit_price":
        await notify_plan_rate_change(plan, old_rate=old_rate, new_rate=float(stored), actor_id=user_id)
    await set_step(user_id, "panel")
    with contextlib.suppress(Exception):
        await event.delete()
    remaining = validate_plan({**plan_model_values(plan), field: stored}, existing_mode=plan.pricing_mode)
    if remaining:
        await event.respond(f"✅ تغییر ذخیره شد.\n⚠️ این پلن هنوز باید اصلاح شود: {remaining}")
    else:
        await event.respond("✅ تغییر ذخیره شد.")
    await _show_plan_after_edit(event, plan.id)


async def _process_reseller_import_username(event: Message, user_id: int, msg: str) -> None:
    username = msg.strip()
    if not username:
        await event.respond("نام کاربری معتبر ارسال کنید.")
        return

    panel_code = as_int(await get_data(user_id, "reseller_import_panel_code"))
    if panel_code is None:
        await event.respond("پنل انتخاب نشده است. دوباره از منو شروع کنید.")
        return

    panel = await PanelsManager().get_panel_by_code(code=panel_code)
    if not panel:
        await event.respond("پنل یافت نشد.")
        return

    existing = await ResellerAccountCRUD().get_by_panel_username(panel_code, username)
    if existing:
        await event.respond("این ادمین از قبل در ربات ثبت شده است. نام کاربری دیگری ارسال کنید.")
        return

    try:
        admin = await find_admin_by_username(panel, username)
    except Exception:
        await event.respond("خطا در دریافت ادمین از پنل. دوباره تلاش کنید.")
        return
    if not admin:
        await event.respond("ادمینی با این نام کاربری در پنل یافت نشد.")
        return

    await set_data(user_id, "reseller_import_username", username)
    await set_step(user_id, "reseller_import_telegram_id")
    with contextlib.suppress(Exception):
        await event.delete()
    await Kenzo.send_message(
        user_id,
        format_panel_admin_preview(admin, panel_name=panel.name),
        parse_mode="markdown",
    )


async def _process_reseller_import_telegram_id(event: Message, user_id: int, msg: str) -> None:
    telegram_id = as_int(msg.replace(",", "").strip())
    if telegram_id is None:
        await event.respond("آیدی عددی معتبر ارسال کنید.")
        return

    user = await UserCRUD().read_user(telegram_id)
    if not user:
        await event.respond(f"کاربر {telegram_id} ربات را استارت نکرده است.")
        return

    panel_code = as_int(await get_data(user_id, "reseller_import_panel_code"))
    if panel_code is None:
        await event.respond("پنل انتخاب نشده است. دوباره از منو شروع کنید.")
        return

    await set_data(user_id, "reseller_import_telegram_id", str(telegram_id))
    with contextlib.suppress(Exception):
        await event.delete()
    await _show_import_plan_picker(event, user_id, panel_code)


async def message_handler_reseller_plans(event: Message):
    if not event.is_private or event.sender_id not in ADMIN_ID:
        return
    msg = (event.message.text or "").strip()
    user_id = event.sender_id

    if msg == states.RESELLER_PLAN_MENU_MESSAGE:
        await Kenzo.send_message(
            user_id,
            "منوی پلن‌های نمایندگی:",
            buttons=reseller_plan_main_menu_buttons(),
        )
        return

    step = await get_step(user_id)

    if step == "reseller_import_username" and msg:
        await _process_reseller_import_username(event, user_id, msg)
        return

    if step == "reseller_import_telegram_id" and msg:
        await _process_reseller_import_telegram_id(event, user_id, msg)
        return

    if step == states.STEP_ADD_FIELD and msg:
        await _process_add_field(event, user_id, msg)
        return

    if step == states.STEP_EDIT_FIELD and msg:
        await _process_edit_field(event, user_id, msg)
        return

    if step == "reseller_plan_edit_btn_text":
        plan_id = int(await get_data(user_id, "reseller_edit_plan_id"))
        if msg.lower() == "/skip":
            await ResellerPlanManager().update_plan(plan_id, display_button_text=None)
        else:
            await ResellerPlanManager().update_plan(plan_id, display_button_text=msg)
        await set_step(user_id, "panel")
        with contextlib.suppress(Exception):
            await event.delete()
        plan = await ResellerPlanManager().get_plan(plan_id)
        if plan:
            await Kenzo.send_message(
                user_id,
                reseller_plan_display_config_text(plan),
                buttons=reseller_plan_display_buttons(plan_id, plan.panel_code),
                parse_mode="markdown",
            )
        return

    if step == "reseller_plan_edit_btn_icon":
        plan_id = int(await get_data(user_id, "reseller_edit_plan_id"))
        icon_id = extract_custom_emoji_document_id(event.message)
        if icon_id is None and msg.lstrip("-").isdigit():
            icon_id = int(msg)
        if icon_id is None:
            await event.respond("ایموجی پریمیوم یا شناسه عددی معتبر ارسال کنید.")
            return
        await ResellerPlanManager().update_plan(plan_id, button_icon=icon_id)
        await set_step(user_id, "panel")
        with contextlib.suppress(Exception):
            await event.delete()
        plan = await ResellerPlanManager().get_plan(plan_id)
        if plan:
            await Kenzo.send_message(
                user_id,
                reseller_plan_display_config_text(plan),
                buttons=reseller_plan_display_buttons(plan_id, plan.panel_code),
                parse_mode="markdown",
            )
        return


async def _filter(event: Message) -> bool:
    if event.sender_id not in ADMIN_ID or not event.is_private:
        return False
    msg = (event.message.text or "").strip()
    if msg == states.RESELLER_PLAN_MENU_MESSAGE:
        return True
    step = (await get_step(event.sender_id)) or ""
    if step == "reseller_plan_edit_btn_icon":
        return bool(msg) or bool(event.message.media)
    return step in states.ADMIN_INPUT_STEPS and bool(msg)


def register(client):
    client.add_event_handler(
        message_handler_reseller_plans,
        events.NewMessage(incoming=True, from_users=ADMIN_ID, func=_filter),
    )
