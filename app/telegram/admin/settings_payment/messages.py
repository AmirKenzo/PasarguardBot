"""Message handlers for admin settings_payment."""

import asyncio

from telethon import events
from telethon.tl.custom import Message

from app import Kenzo
from app.db.crud.cards import ManualCardManager
from app.db.crud.settings import SettingsManager
from app.telegram.admin.settings_payment import keyboards, texts
from app.telegram.admin.settings_payment.callbacks import _maar_crud, _maar_menu
from app.telegram.state import clear_user, get_data, get_step, set_data, set_step
from config import ADMIN_ID


async def delete_message(event, offset=0, delay=0):
    """
    Deletes a message based on the given offset after an optional delay.
    If offset = 0, the current message will be deleted.
    If offset = -1, the previous message will be deleted.
    """
    try:
        target_message_id = event.message.id + offset

        if delay > 0:
            await asyncio.sleep(delay)

        await event.client.delete_messages(event.chat_id, target_message_id)
    except Exception:
        pass


async def message_handler_settings_payment(event: Message):
    msg = event.message.text
    user_id = event.sender_id

    if msg in [texts.GATEWAY_SETTINGS_TRIGGER]:
        await set_step(user_id=event.sender_id, step="SettingsCardToCard")
        settings = await SettingsManager().get_settings()
        cards = await ManualCardManager().get_all_cards()
        active = next((c for c in cards if c.active), None)
        random_mode_status = (
            texts.RANDOM_MODE_ACTIVE if settings.manual_card_random_mode else texts.RANDOM_MODE_INACTIVE
        )
        await Kenzo.send_message(
            entity=user_id,
            message=texts.gateway_settings_message(texts.manual_card_info(active), random_mode_status, settings),
            buttons=keyboards.gateway_settings_buttons(settings),
        )
    elif await get_step(event.sender_id) == "add_card_number" and msg:
        await set_data(event.sender_id, "new_card_number", msg)
        await set_step(event.sender_id, "add_card_name")
        await event.respond(texts.CARD_NAME_PROMPT)

    elif await get_step(event.sender_id) == "add_card_name" and msg:
        number = await get_data(event.sender_id, "new_card_number")
        await ManualCardManager().add_card(number=number, name=msg, active=True)
        await clear_user(event.sender_id)
        await set_step(event.sender_id, "SettingsCardToCard")
        await event.respond(texts.CARD_ADDED_SUCCESS)

    elif await get_step(event.sender_id) == "set_manual_min" and msg.isdigit():
        await set_data(event.sender_id, "manual_deposit_min", int(msg))
        await set_step(event.sender_id, "set_manual_max")
        await event.respond(texts.MANUAL_MAX_PROMPT)
    elif await get_step(event.sender_id) == "set_manual_min":
        await event.respond(texts.NUMERIC_ONLY)

    elif await get_step(event.sender_id) == "set_manual_max" and msg.isdigit():
        min_val = await get_data(event.sender_id, "manual_deposit_min")
        settings = await SettingsManager().get_settings()
        await SettingsManager().update_setting(
            settings.id,
            manual_deposit_min=int(min_val),
            manual_deposit_max=int(msg),
        )
        await clear_user(event.sender_id)
        await set_step(event.sender_id, "SettingsCardToCard")
        await event.respond(texts.MANUAL_LIMITS_SAVED, buttons=keyboards.back_to_settings_card_row())

    elif await get_step(event.sender_id) == "set_manual_max":
        await event.respond(texts.NUMERIC_ONLY)

    elif await get_step(event.sender_id) == "set_crypto_min" and msg.isdigit():
        await set_data(event.sender_id, "crypto_deposit_min", int(msg))
        await set_step(event.sender_id, "set_crypto_max")
        await event.respond(texts.CRYPTO_MIN_PROMPT, buttons=keyboards.crypto_limit_back_button())

    elif await get_step(event.sender_id) == "set_crypto_min":
        await event.respond(texts.NUMERIC_ONLY)

    elif await get_step(event.sender_id) == "set_crypto_max" and msg.isdigit():
        min_val = await get_data(event.sender_id, "crypto_deposit_min")
        settings = await SettingsManager().get_settings()
        await SettingsManager().update_setting(
            settings.id,
            crypto_deposit_min=int(min_val),
            crypto_deposit_max=int(msg),
        )
        await clear_user(event.sender_id)
        await set_step(event.sender_id, "panel")
        settings = await SettingsManager().get_settings()
        await event.respond(texts.CRYPTO_LIMITS_SAVED, buttons=keyboards.gateway_settings_buttons(settings))

    elif await get_step(event.sender_id) == "set_crypto_max":
        await event.respond(texts.NUMERIC_ONLY)

    elif await get_step(event.sender_id) == "set_reseller_min_wallet" and msg.isdigit():
        settings = await SettingsManager().get_settings()
        await SettingsManager().update_setting(
            settings.id,
            reseller_min_wallet_balance=int(msg),
        )
        await clear_user(event.sender_id)
        await set_step(event.sender_id, "SettingsCardToCard")
        await event.respond(texts.RESELLER_MIN_WALLET_SAVED, buttons=keyboards.back_to_settings_card_row())

    elif await get_step(event.sender_id) == "set_reseller_min_wallet":
        await event.respond(texts.NUMERIC_ONLY)

    elif await get_step(event.sender_id) == "set_manual_bonus_percent" and msg.isdigit():
        percent = int(msg)
        if percent < 0 or percent > 100:
            await delete_message(event, offset=-1)
            await delete_message(event)
            await event.respond(texts.PERCENT_RANGE_ERROR, buttons=keyboards.back_to_bonus_menu_button())
            raise events.StopPropagation
        settings = await SettingsManager().get_settings()
        await SettingsManager().update_setting(settings.id, manual_bonus_percent=percent)
        await set_step(event.sender_id, "SettingsCardToCard")
        settings = await SettingsManager().get_settings()
        bonus_text, buttons = await keyboards.get_bonus_settings_menu(settings)
        await delete_message(event, offset=-1)
        await delete_message(event)
        await event.respond(
            texts.MANUAL_BONUS_SET_TEMPLATE.format(percent=percent, bonus_text=bonus_text),
            buttons=buttons,
        )
    elif await get_step(event.sender_id) == "set_manual_bonus_percent":
        await delete_message(event, offset=-1)
        await delete_message(event)
        await event.respond(texts.NUMERIC_ONLY, buttons=keyboards.back_to_bonus_menu_button())

    elif await get_step(event.sender_id) == "set_crypto_bonus_percent" and msg.isdigit():
        percent = int(msg)
        if percent < 0 or percent > 100:
            await delete_message(event, offset=-1)
            await delete_message(event)
            await event.respond(texts.PERCENT_RANGE_ERROR, buttons=keyboards.back_to_bonus_menu_button())
            raise events.StopPropagation
        settings = await SettingsManager().get_settings()
        await SettingsManager().update_setting(settings.id, crypto_bonus_percent=percent)
        await set_step(event.sender_id, "SettingsCardToCard")
        settings = await SettingsManager().get_settings()
        bonus_text, buttons = await keyboards.get_bonus_settings_menu(settings)
        await delete_message(event, offset=-1)
        await delete_message(event)
        await event.respond(
            texts.CRYPTO_BONUS_SET_TEMPLATE.format(percent=percent, bonus_text=bonus_text),
            buttons=buttons,
        )
    elif await get_step(event.sender_id) == "set_crypto_bonus_percent":
        await delete_message(event, offset=-1)
        await delete_message(event)
        await event.respond(texts.NUMERIC_ONLY, buttons=keyboards.back_to_bonus_menu_button())

    elif await get_step(event.sender_id) == "set_stars_bonus_percent" and msg.isdigit():
        percent = int(msg)
        if percent < 0 or percent > 100:
            await delete_message(event, offset=-1)
            await delete_message(event)
            await event.respond(texts.PERCENT_RANGE_ERROR, buttons=keyboards.back_to_bonus_menu_button())
            raise events.StopPropagation
        settings = await SettingsManager().get_settings()
        await SettingsManager().update_setting(settings.id, stars_bonus_percent=percent)
        await set_step(event.sender_id, "SettingsCardToCard")
        settings = await SettingsManager().get_settings()
        bonus_text, buttons = await keyboards.get_bonus_settings_menu(settings)
        await delete_message(event, offset=-1)
        await delete_message(event)
        await event.respond(
            texts.STARS_BONUS_SET_TEMPLATE.format(percent=percent, bonus_text=bonus_text),
            buttons=buttons,
        )
    elif await get_step(event.sender_id) == "set_stars_bonus_percent":
        await delete_message(event, offset=-1)
        await delete_message(event)
        await event.respond(texts.NUMERIC_ONLY, buttons=keyboards.back_to_bonus_menu_button())

    elif await get_step(event.sender_id) == "maar_add_min" and msg.isdigit():
        await set_data(event.sender_id, "maar_min", int(msg))
        await set_step(event.sender_id, "maar_add_max")
        await event.respond(texts.MAAR_ADD_MAX_PROMPT)
    elif await get_step(event.sender_id) == "maar_add_max":
        max_val = None if msg.lower() in ("none", "-", "") else int(msg) if msg.isdigit() else None
        if max_val is None and msg.lower() not in ("none", "-", ""):
            await event.respond(texts.MAAR_NUMERIC_OR_NONE)
            return
        await set_data(event.sender_id, "maar_max", max_val)
        await set_step(event.sender_id, "maar_add_delay")
        await event.respond(texts.MAAR_ADD_DELAY_PROMPT)
    elif await get_step(event.sender_id) == "maar_add_delay" and msg.isdigit():
        await _maar_crud.create(
            min_successful_tx=int(await get_data(event.sender_id, "maar_min")),
            max_successful_tx=await get_data(event.sender_id, "maar_max"),
            auto_approve_delay_minutes=int(msg),
        )
        await clear_user(event.sender_id)
        await set_step(event.sender_id, "SettingsCardToCard")
        menu_text, buttons = await _maar_menu()
        await event.respond(menu_text, buttons=buttons)
    elif await get_step(event.sender_id) in ("maar_edit_min", "maar_edit_max", "maar_edit_delay"):
        rule_id = int(await get_data(event.sender_id, "maar_rule_id"))
        field = {
            "maar_edit_min": "min_successful_tx",
            "maar_edit_max": "max_successful_tx",
            "maar_edit_delay": "auto_approve_delay_minutes",
        }[await get_step(event.sender_id)]
        if field == "max_successful_tx":
            val = None if msg.lower() in ("none", "-") else int(msg) if msg.isdigit() else None
            if val is None and msg.lower() not in ("none", "-"):
                await event.respond(texts.MAAR_NUMERIC_OR_NONE)
                return
        elif not msg.isdigit():
            await event.respond(texts.MAAR_NUMERIC_ONLY)
            return
        else:
            val = int(msg)
        await _maar_crud.update(rule_id, **{field: val})
        await clear_user(event.sender_id)
        await set_step(event.sender_id, "SettingsCardToCard")
        await event.respond(texts.MAAR_SAVED, buttons=keyboards.maar_saved_back_button(rule_id))


def register(client):
    client.add_event_handler(
        message_handler_settings_payment,
        events.NewMessage(incoming=True, from_users=ADMIN_ID),
    )
