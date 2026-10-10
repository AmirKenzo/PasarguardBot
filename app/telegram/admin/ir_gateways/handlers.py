"""Admin settings for every Iranian direct gateway through one generic menu.

Callback data: `irgw_admin` (gateway list), `irgw_admin:<key>` (gateway menu),
`irgw_admin:<key>:<action>` (toggle, sandbox, merchant, test, limits, bonus, bonus_percent).
During text input the gateway key is kept in the admin's state.
"""

from __future__ import annotations

from telethon import Button, events
from telethon.tl.custom import Message

from app.db.crud.settings import SettingsManager
from app.services.payments.ir_gateways import config
from app.services.payments.ir_gateways.providers import GATEWAYS
from app.services.payments.ir_gateways.service import test_connection
from app.telegram.state import clear_user, get_data, get_step, set_data, set_step
from config import ADMIN_ID

MENU = "irgw_admin"
_PREFIX = "irgw_admin:"

STEP_MERCHANT = "irgw_set_merchant"
STEP_MIN = "irgw_set_min"
STEP_MAX = "irgw_set_max"
STEP_BONUS = "irgw_set_bonus"
_STEPS = frozenset({STEP_MERCHANT, STEP_MIN, STEP_MAX, STEP_BONUS})
_KEY_DATA = "irgw_admin_key"
_MIN_DATA = "irgw_admin_min"


def _status_icon(settings, key: str) -> str:
    if config.is_ready(settings, key):
        return "🧪" if config.is_sandbox(settings, key) else "✅"
    return "❌"


def _list_text() -> str:
    return (
        "🏦 <b>درگاه‌های پرداخت ایرانی</b>\n\n"
        "درگاه مورد نظر را برای تنظیم انتخاب کنید.\n"
        "✅ فعال (واقعی) | 🧪 فعال (تست، فقط ادمین) | ❌ غیرفعال"
    )


def _list_buttons(settings) -> list:
    rows = [
        [Button.inline(f"{_status_icon(settings, key)} {p.emoji} {p.title}", data=f"{_PREFIX}{key}")]
        for key, p in GATEWAYS.items()
    ]
    rows.append([Button.inline("🔙 بازگشت", data="BackTOSettingsCardToCard")])
    return rows


def _menu_text(settings, key: str) -> str:
    provider = GATEWAYS[key]
    values = config.gateway_settings(settings, key)
    sandbox = bool(values["sandbox"])
    hook = config.callback_url(key)
    merchant = config.stored_merchant(settings, key)
    return (
        f"{provider.emoji} <b>تنظیمات درگاه {provider.title}</b>\n\n"
        f"📶 <b>وضعیت:</b> {'فعال ✅' if values['enabled'] else 'غیرفعال ❌'}\n"
        f"🧪 <b>حالت:</b> {'تست — فقط ادمین‌ها می‌بینند' if sandbox else 'واقعی (برای همه کاربران)'}\n"
        f"🔑 <b>مرچنت:</b> <code>{config.mask_merchant(merchant) or 'تنظیم نشده'}</code>\n"
        f"💰 <b>محدوده شارژ:</b> {int(values['deposit_min'] or 0):,} تا {int(values['deposit_max'] or 0):,} تومان\n"
        f"🎁 <b>بونوس:</b> {int(values['bonus_percent'] or 0)}% {'✅' if values['bonus_enabled'] else '❌'}\n\n"
        "🔗 <b>آدرس بازگشت (Callback):</b>\n"
        + (f"<code>{hook}</code>" if hook else "⚠️ WEBAPP_URL با https تنظیم نشده؛ درگاه بدون آن کار نمی‌کند.")
        + f"\n\nℹ️ حالت تست: {provider.sandbox_hint}؛ پرداخت واقعی انجام نمی‌شود.\n"
        f"برای حالت واقعی: {provider.merchant_hint}، سپس حالت را «واقعی» کنید."
    )


def _menu_buttons(settings, key: str) -> list:
    values = config.gateway_settings(settings, key)
    base = f"{_PREFIX}{key}:"
    return [
        [
            Button.inline(
                "❌ خاموش کردن درگاه" if values["enabled"] else "✅ روشن کردن درگاه",
                data=f"{base}toggle",
            )
        ],
        [Button.inline(f"🧪 حالت: {'تست' if values['sandbox'] else 'واقعی'} (تغییر)", data=f"{base}sandbox")],
        [Button.inline("🔑 مرچنت", data=f"{base}merchant")],
        [Button.inline("🧪 تست اتصال", data=f"{base}test")],
        [Button.inline("💰 محدوده مبلغ شارژ", data=f"{base}limits")],
        [
            Button.inline(f"🎁 بونوس {'✅' if values['bonus_enabled'] else '❌'}", data=f"{base}bonus"),
            Button.inline("📝 درصد بونوس", data=f"{base}bonus_percent"),
        ],
        [Button.inline("🔙 بازگشت", data=MENU)],
    ]


def _back_row(key: str) -> list:
    return [[Button.inline("🔙 بازگشت", data=f"{_PREFIX}{key}")]]


async def _show(event, text: str, buttons: list, *, edit: bool = True) -> None:
    if edit:
        try:
            await event.edit(text, buttons=buttons, parse_mode="html")
            return
        except Exception:
            pass
    await event.respond(text, buttons=buttons, parse_mode="html")


async def _save(settings, key: str, **changes) -> None:
    await SettingsManager().update_setting(settings.id, ir_gateways=config.updated_settings(settings, key, **changes))


def _callback_filter(event: events.CallbackQuery.Event) -> bool:
    if event.sender_id not in ADMIN_ID:
        return False
    data = event.data.decode("utf-8")
    return data == MENU or data.startswith(_PREFIX)


async def ir_gateways_admin_callback(event: events.CallbackQuery.Event):
    data = event.data.decode("utf-8")
    settings = await SettingsManager().get_settings()
    if data == MENU:
        await set_step(event.sender_id, "SettingsCardToCard")
        await _show(event, _list_text(), _list_buttons(settings))
        raise events.StopPropagation

    key, _, action = data.removeprefix(_PREFIX).partition(":")
    provider = GATEWAYS.get(key)
    if provider is None:
        await event.answer("درگاه نامعتبر است.", alert=True)
        raise events.StopPropagation
    values = config.gateway_settings(settings, key)

    if action == "toggle":
        await _save(settings, key, enabled=not values["enabled"])
    elif action == "sandbox":
        going_live = bool(values["sandbox"])
        if going_live and not provider.is_valid_merchant(config.stored_merchant(settings, key)):
            await event.answer(f"برای حالت واقعی، اول مرچنت {provider.title} را ثبت کنید.", alert=True)
            raise events.StopPropagation
        await _save(settings, key, sandbox=not going_live)
    elif action == "bonus":
        await _save(settings, key, bonus_enabled=not values["bonus_enabled"])
    elif action == "test":
        sandbox = bool(values["sandbox"])
        if not config.merchant_for(settings, key, sandbox):
            await event.answer(f"مرچنت {provider.title} تنظیم نشده است.", alert=True)
            raise events.StopPropagation
        ok, message = await test_connection(key, config.stored_merchant(settings, key), sandbox)
        await event.answer(f"{'✅' if ok else '❌'} {message}"[:200], alert=True)
        raise events.StopPropagation
    elif action in ("merchant", "limits", "bonus_percent"):
        step, prompt = {
            "merchant": (STEP_MERCHANT, f"🔑 مرچنت درگاه {provider.title} را ارسال کنید:\n{provider.merchant_hint}"),
            "limits": (STEP_MIN, "💰 حداقل مبلغ شارژ را به تومان وارد کنید:"),
            "bonus_percent": (STEP_BONUS, "🎁 درصد بونوس را وارد کنید (۰ تا ۱۰۰):"),
        }[action]
        await set_data(event.sender_id, _KEY_DATA, key)
        await set_step(event.sender_id, step)
        await event.edit(prompt, buttons=_back_row(key))
        raise events.StopPropagation

    settings = await SettingsManager().get_settings()
    await _show(event, _menu_text(settings, key), _menu_buttons(settings, key))
    raise events.StopPropagation


async def _message_filter(event) -> bool:
    if event.sender_id not in ADMIN_ID or not event.is_private:
        return False
    return await get_step(event.sender_id) in _STEPS


async def ir_gateways_admin_message(event: Message):
    step = await get_step(event.sender_id)
    text = (event.message.message or "").strip()
    key = str(await get_data(event.sender_id, _KEY_DATA) or "")
    provider = GATEWAYS.get(key)
    if provider is None:
        await clear_user(event.sender_id)
        await set_step(event.sender_id, "SettingsCardToCard")
        raise events.StopPropagation
    settings = await SettingsManager().get_settings()

    if step == STEP_MERCHANT:
        if not provider.is_valid_merchant(text):
            await event.respond(f"❌ مرچنت نامعتبر است.\n{provider.merchant_hint}", buttons=_back_row(key))
            raise events.StopPropagation
        await _save(settings, key, merchant=text)
        ok, message = await test_connection(key, text, False)
        await event.respond(f"✅ مرچنت ذخیره شد.\n{'🟢' if ok else '🔴'} تست اتصال (واقعی): {message}")
    else:
        value = text.replace(",", "")
        if not value.isdigit():
            await event.respond("❌ فقط عدد وارد کنید.", buttons=_back_row(key))
            raise events.StopPropagation
        number = int(value)
        if step == STEP_MIN:
            if number < 1000:
                await event.respond("❌ حداقل مبلغ ۱,۰۰۰ تومان است.", buttons=_back_row(key))
                raise events.StopPropagation
            await set_data(event.sender_id, _MIN_DATA, number)
            await set_step(event.sender_id, STEP_MAX)
            await event.respond("💰 حداکثر مبلغ شارژ را به تومان وارد کنید:", buttons=_back_row(key))
            raise events.StopPropagation
        if step == STEP_MAX:
            min_value = int(await get_data(event.sender_id, _MIN_DATA) or 0)
            if number < min_value:
                await event.respond("❌ حداکثر باید بیشتر از حداقل باشد.", buttons=_back_row(key))
                raise events.StopPropagation
            await _save(settings, key, deposit_min=min_value, deposit_max=number)
            await event.respond("✅ محدوده مبلغ شارژ ذخیره شد.")
        else:
            if number > 100:
                await event.respond("❌ درصد باید بین ۰ تا ۱۰۰ باشد.", buttons=_back_row(key))
                raise events.StopPropagation
            await _save(settings, key, bonus_percent=number)
            await event.respond("✅ درصد بونوس ذخیره شد.")

    await clear_user(event.sender_id)
    await set_step(event.sender_id, "SettingsCardToCard")
    settings = await SettingsManager().get_settings()
    await _show(event, _menu_text(settings, key), _menu_buttons(settings, key), edit=False)
    raise events.StopPropagation


def register(client):
    client.add_event_handler(ir_gateways_admin_callback, events.CallbackQuery(func=_callback_filter))
    client.add_event_handler(ir_gateways_admin_message, events.NewMessage(incoming=True, func=_message_filter))
