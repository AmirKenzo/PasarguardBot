"""Admin TonPays settings: on/off, gateway type, API keys, connection test, limits and bonus."""

from __future__ import annotations

from telethon import Button, events
from telethon.tl.custom import Message

from app.db.crud.settings import SettingsManager
from app.services.payments.tonpays import test_connection
from app.services.payments.tonpays_config import (
    MODE_CUSTOM,
    MODE_STANDARD,
    api_key_for,
    callback_url,
    gateway_mode,
    mask_key,
)
from app.telegram.state import clear_user, get_data, get_step, set_data, set_step
from config import ADMIN_ID

MENU = "tonpays_admin"
_PREFIX = "tonpays_admin:"

STEP_KEY = "tonpays_set_key"
STEP_CUSTOM_KEY = "tonpays_set_custom_key"
STEP_MIN = "tonpays_set_min"
STEP_MAX = "tonpays_set_max"
STEP_BONUS = "tonpays_set_bonus"
_STEPS = frozenset({STEP_KEY, STEP_CUSTOM_KEY, STEP_MIN, STEP_MAX, STEP_BONUS})


def _menu_text(settings) -> str:
    mode = gateway_mode(settings)
    hook = callback_url()
    return (
        "💎 <b>تنظیمات درگاه TonPays</b>\n\n"
        f"📶 <b>وضعیت:</b> {'فعال ✅' if settings.tonpays_enabled else 'غیرفعال ❌'}\n"
        f"🧬 <b>نوع درگاه:</b> {'کاستوم (کارت داخل ربات)' if mode == MODE_CUSTOM else 'معمولی (پرداخت در ربات TonPays)'}\n"
        f"🔑 <b>کلید معمولی:</b> <code>{mask_key(settings.tonpays_api_key)}</code>\n"
        f"🔑 <b>کلید کاستوم تلگرام:</b> <code>{mask_key(settings.tonpays_custom_key)}</code>\n"
        f"💰 <b>محدوده شارژ:</b> {int(settings.tonpays_deposit_min or 0):,} تا "
        f"{int(settings.tonpays_deposit_max or 0):,} تومان\n"
        f"🎁 <b>بونوس:</b> {int(settings.tonpays_bonus_percent or 0)}% "
        f"{'✅' if settings.tonpays_bonus_enabled else '❌'}\n\n"
        "🔗 <b>آدرس وب‌هوک (در پنل TonPays ثبت کنید):</b>\n"
        + (
            f"<code>{hook}</code>"
            if hook
            else "⚠️ WEBAPP_URL با https تنظیم نشده؛ تأیید فقط با استعلام دوره‌ای انجام می‌شود."
        )
        + "\n\nکلید را از پنل فروشگاه TonPays (تنظیمات ← کلید API) بردارید."
    )


def _menu_buttons(settings) -> list:
    mode = gateway_mode(settings)
    return [
        [
            Button.inline(
                "❌ خاموش کردن درگاه" if settings.tonpays_enabled else "✅ روشن کردن درگاه",
                data=f"{_PREFIX}toggle",
            )
        ],
        [
            Button.inline(
                f"🧬 نوع: {'کاستوم' if mode == MODE_CUSTOM else 'معمولی'} (تغییر)",
                data=f"{_PREFIX}mode",
            )
        ],
        [
            Button.inline("🔑 کلید معمولی", data=f"{_PREFIX}key"),
            Button.inline("🔑 کلید کاستوم", data=f"{_PREFIX}custom_key"),
        ],
        [Button.inline("🧪 تست اتصال", data=f"{_PREFIX}test")],
        [Button.inline("💰 محدوده مبلغ شارژ", data=f"{_PREFIX}limits")],
        [
            Button.inline(f"🎁 بونوس {'✅' if settings.tonpays_bonus_enabled else '❌'}", data=f"{_PREFIX}bonus"),
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


async def tonpays_admin_callback(event: events.CallbackQuery.Event):
    data = event.data.decode("utf-8")
    action = data.removeprefix(_PREFIX) if data != MENU else ""
    manager = SettingsManager()
    settings = await manager.get_settings()

    if action == "toggle":
        await manager.update_setting(settings.id, tonpays_enabled=not settings.tonpays_enabled)
    elif action == "mode":
        new_mode = MODE_STANDARD if gateway_mode(settings) == MODE_CUSTOM else MODE_CUSTOM
        await manager.update_setting(settings.id, tonpays_mode=new_mode)
    elif action == "bonus":
        await manager.update_setting(settings.id, tonpays_bonus_enabled=not settings.tonpays_bonus_enabled)
    elif action == "test":
        mode = gateway_mode(settings)
        key = api_key_for(settings, mode)
        if not key:
            await event.answer("کلید درگاه انتخاب‌شده تنظیم نشده است.", alert=True)
            raise events.StopPropagation
        ok, message = await test_connection(key, mode)
        await event.answer(f"{'✅' if ok else '❌'} {message}", alert=True)
        raise events.StopPropagation
    elif action in ("key", "custom_key", "limits", "bonus_percent"):
        step, prompt = {
            "key": (STEP_KEY, "🔑 کلید API معمولی TonPays را ارسال کنید:"),
            "custom_key": (STEP_CUSTOM_KEY, "🔑 کلید تلگرام درگاه کاستوم TonPays را ارسال کنید:"),
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


async def tonpays_admin_message(event: Message):
    step = await get_step(event.sender_id)
    text = (event.message.message or "").strip()
    manager = SettingsManager()
    settings = await manager.get_settings()

    if step in (STEP_KEY, STEP_CUSTOM_KEY):
        if not text or len(text) > 256 or " " in text:
            await event.respond("❌ کلید نامعتبر است. دوباره ارسال کنید.", buttons=_back_row())
            raise events.StopPropagation
        field = "tonpays_api_key" if step == STEP_KEY else "tonpays_custom_key"
        await manager.update_setting(settings.id, **{field: text})
        ok, message = await test_connection(text, MODE_STANDARD if step == STEP_KEY else MODE_CUSTOM)
        await event.respond(f"✅ کلید ذخیره شد.\n{'🟢' if ok else '🔴'} تست اتصال: {message}")
    elif step in (STEP_MIN, STEP_MAX, STEP_BONUS):
        value = text.replace(",", "")
        if not value.isdigit():
            await event.respond("❌ فقط عدد وارد کنید.", buttons=_back_row())
            raise events.StopPropagation
        number = int(value)
        if step == STEP_MIN:
            await set_data(event.sender_id, "tonpays_min", number)
            await set_step(event.sender_id, STEP_MAX)
            await event.respond("💰 حداکثر مبلغ شارژ را به تومان وارد کنید:", buttons=_back_row())
            raise events.StopPropagation
        if step == STEP_MAX:
            min_value = int(await get_data(event.sender_id, "tonpays_min") or 0)
            if number < min_value:
                await event.respond("❌ حداکثر باید بیشتر از حداقل باشد.", buttons=_back_row())
                raise events.StopPropagation
            await manager.update_setting(settings.id, tonpays_deposit_min=min_value, tonpays_deposit_max=number)
            await event.respond("✅ محدوده مبلغ شارژ ذخیره شد.")
        else:
            if number > 100:
                await event.respond("❌ درصد باید بین ۰ تا ۱۰۰ باشد.", buttons=_back_row())
                raise events.StopPropagation
            await manager.update_setting(settings.id, tonpays_bonus_percent=number)
            await event.respond("✅ درصد بونوس ذخیره شد.")

    await clear_user(event.sender_id)
    await set_step(event.sender_id, "SettingsCardToCard")
    await _show_menu(event, edit=False)
    raise events.StopPropagation


def register(client):
    client.add_event_handler(tonpays_admin_callback, events.CallbackQuery(func=_callback_filter))
    client.add_event_handler(tonpays_admin_message, events.NewMessage(incoming=True, func=_message_filter))
