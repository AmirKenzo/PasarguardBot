"""Admin Zarinpal settings: on/off, test (sandbox) mode, merchant id, connection test, limits and bonus."""

from __future__ import annotations

from telethon import Button, events
from telethon.tl.custom import Message

from app.db.crud.settings import SettingsManager
from app.services.payments.zarinpal import test_connection
from app.services.payments.zarinpal_config import (
    callback_url,
    is_sandbox,
    is_valid_merchant_id,
    mask_merchant,
    merchant_id_for,
    stored_merchant_id,
)
from app.telegram.state import clear_user, get_data, get_step, set_data, set_step
from config import ADMIN_ID

MENU = "zarinpal_admin"
_PREFIX = "zarinpal_admin:"

STEP_MERCHANT = "zarinpal_set_merchant"
STEP_MIN = "zarinpal_set_min"
STEP_MAX = "zarinpal_set_max"
STEP_BONUS = "zarinpal_set_bonus"
_STEPS = frozenset({STEP_MERCHANT, STEP_MIN, STEP_MAX, STEP_BONUS})


def _menu_text(settings) -> str:
    sandbox = is_sandbox(settings)
    hook = callback_url()
    merchant = stored_merchant_id(settings)
    return (
        "🟡 <b>تنظیمات درگاه زرین‌پال</b>\n\n"
        f"📶 <b>وضعیت:</b> {'فعال ✅' if settings.zarinpal_enabled else 'غیرفعال ❌'}\n"
        f"🧪 <b>حالت:</b> {'تست (sandbox) — فقط ادمین‌ها می‌بینند' if sandbox else 'واقعی (برای همه کاربران)'}\n"
        f"🔑 <b>مرچنت کد:</b> <code>{mask_merchant(merchant) or 'تنظیم نشده'}</code>\n"
        f"💰 <b>محدوده شارژ:</b> {int(settings.zarinpal_deposit_min or 0):,} تا "
        f"{int(settings.zarinpal_deposit_max or 0):,} تومان\n"
        f"🎁 <b>بونوس:</b> {int(settings.zarinpal_bonus_percent or 0)}% "
        f"{'✅' if settings.zarinpal_bonus_enabled else '❌'}\n\n"
        "🔗 <b>آدرس بازگشت (Callback):</b>\n"
        + (f"<code>{hook}</code>" if hook else "⚠️ WEBAPP_URL با https تنظیم نشده؛ درگاه بدون آن کار نمی‌کند.")
        + "\n\nℹ️ در حالت تست نیازی به مرچنت کد نیست و پرداخت واقعی انجام نمی‌شود؛ "
        "برای استفاده واقعی، مرچنت کد را از پنل زرین‌پال بردارید و حالت را «واقعی» کنید."
    )


def _menu_buttons(settings) -> list:
    sandbox = is_sandbox(settings)
    return [
        [
            Button.inline(
                "❌ خاموش کردن درگاه" if settings.zarinpal_enabled else "✅ روشن کردن درگاه",
                data=f"{_PREFIX}toggle",
            )
        ],
        [Button.inline(f"🧪 حالت: {'تست' if sandbox else 'واقعی'} (تغییر)", data=f"{_PREFIX}sandbox")],
        [Button.inline("🔑 مرچنت کد", data=f"{_PREFIX}merchant")],
        [Button.inline("🧪 تست اتصال", data=f"{_PREFIX}test")],
        [Button.inline("💰 محدوده مبلغ شارژ", data=f"{_PREFIX}limits")],
        [
            Button.inline(f"🎁 بونوس {'✅' if settings.zarinpal_bonus_enabled else '❌'}", data=f"{_PREFIX}bonus"),
            Button.inline("📝 درصد بونوس", data=f"{_PREFIX}bonus_percent"),
        ],
        [Button.inline("🔙 بازگشت", data="BackTOSettingsCardToCard")],
    ]


def _back_row() -> list:
    return [[Button.inline("🔙 بازگشت", data=MENU)]]


async def _show_menu(event, *, edit: bool = True) -> None:
    settings = await SettingsManager().get_settings()
    text, buttons = _menu_text(settings), _menu_buttons(settings)
    if edit:
        try:
            await event.edit(text, buttons=buttons, parse_mode="html")
            return
        except Exception:
            pass
    await event.respond(text, buttons=buttons, parse_mode="html")


def _callback_filter(event: events.CallbackQuery.Event) -> bool:
    if event.sender_id not in ADMIN_ID:
        return False
    data = event.data.decode("utf-8")
    return data == MENU or data.startswith(_PREFIX)


async def zarinpal_admin_callback(event: events.CallbackQuery.Event):
    data = event.data.decode("utf-8")
    action = data.removeprefix(_PREFIX) if data != MENU else ""
    manager = SettingsManager()
    settings = await manager.get_settings()

    if action == "toggle":
        await manager.update_setting(settings.id, zarinpal_enabled=not settings.zarinpal_enabled)
    elif action == "sandbox":
        going_live = is_sandbox(settings)
        if going_live and not is_valid_merchant_id(stored_merchant_id(settings)):
            await event.answer("برای حالت واقعی، اول مرچنت کد معتبر (UUID) ثبت کنید.", alert=True)
            raise events.StopPropagation
        await manager.update_setting(settings.id, zarinpal_sandbox=not going_live)
    elif action == "bonus":
        await manager.update_setting(settings.id, zarinpal_bonus_enabled=not settings.zarinpal_bonus_enabled)
    elif action == "test":
        merchant = merchant_id_for(settings)
        if not merchant:
            await event.answer("مرچنت کد تنظیم نشده است.", alert=True)
            raise events.StopPropagation
        ok, message = await test_connection(merchant, is_sandbox(settings))
        await event.answer(f"{'✅' if ok else '❌'} {message}"[:200], alert=True)
        raise events.StopPropagation
    elif action in ("merchant", "limits", "bonus_percent"):
        step, prompt = {
            "merchant": (STEP_MERCHANT, "🔑 مرچنت کد زرین‌پال (۳۶ کاراکتر) را ارسال کنید:"),
            "limits": (STEP_MIN, "💰 حداقل مبلغ شارژ را به تومان وارد کنید:"),
            "bonus_percent": (STEP_BONUS, "🎁 درصد بونوس را وارد کنید (۰ تا ۱۰۰):"),
        }[action]
        await set_step(event.sender_id, step)
        await event.edit(prompt, buttons=_back_row())
        raise events.StopPropagation

    if data == MENU:
        await set_step(event.sender_id, "SettingsCardToCard")
    await _show_menu(event)
    raise events.StopPropagation


async def _message_filter(event) -> bool:
    if event.sender_id not in ADMIN_ID or not event.is_private:
        return False
    return await get_step(event.sender_id) in _STEPS


async def zarinpal_admin_message(event: Message):
    step = await get_step(event.sender_id)
    text = (event.message.message or "").strip()
    manager = SettingsManager()
    settings = await manager.get_settings()

    if step == STEP_MERCHANT:
        if not is_valid_merchant_id(text):
            await event.respond("❌ مرچنت کد باید ۳۶ کاراکتر به شکل UUID باشد. دوباره ارسال کنید.", buttons=_back_row())
            raise events.StopPropagation
        await manager.update_setting(settings.id, zarinpal_merchant_id=text)
        ok, message = await test_connection(text, is_sandbox(settings))
        await event.respond(f"✅ مرچنت کد ذخیره شد.\n{'🟢' if ok else '🔴'} تست اتصال: {message}")
    elif step in (STEP_MIN, STEP_MAX, STEP_BONUS):
        value = text.replace(",", "")
        if not value.isdigit():
            await event.respond("❌ فقط عدد وارد کنید.", buttons=_back_row())
            raise events.StopPropagation
        number = int(value)
        if step == STEP_MIN:
            if number < 1000:
                await event.respond("❌ حداقل مبلغ در زرین‌پال ۱,۰۰۰ تومان است.", buttons=_back_row())
                raise events.StopPropagation
            await set_data(event.sender_id, "zarinpal_min", number)
            await set_step(event.sender_id, STEP_MAX)
            await event.respond("💰 حداکثر مبلغ شارژ را به تومان وارد کنید:", buttons=_back_row())
            raise events.StopPropagation
        if step == STEP_MAX:
            min_value = int(await get_data(event.sender_id, "zarinpal_min") or 0)
            if number < min_value:
                await event.respond("❌ حداکثر باید بیشتر از حداقل باشد.", buttons=_back_row())
                raise events.StopPropagation
            await manager.update_setting(settings.id, zarinpal_deposit_min=min_value, zarinpal_deposit_max=number)
            await event.respond("✅ محدوده مبلغ شارژ ذخیره شد.")
        else:
            if number > 100:
                await event.respond("❌ درصد باید بین ۰ تا ۱۰۰ باشد.", buttons=_back_row())
                raise events.StopPropagation
            await manager.update_setting(settings.id, zarinpal_bonus_percent=number)
            await event.respond("✅ درصد بونوس ذخیره شد.")

    await clear_user(event.sender_id)
    await set_step(event.sender_id, "SettingsCardToCard")
    await _show_menu(event, edit=False)
    raise events.StopPropagation


def register(client):
    client.add_event_handler(zarinpal_admin_callback, events.CallbackQuery(func=_callback_filter))
    client.add_event_handler(zarinpal_admin_message, events.NewMessage(incoming=True, func=_message_filter))
