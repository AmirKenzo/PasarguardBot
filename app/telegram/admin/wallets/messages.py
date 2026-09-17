"""Admin: crypto wallet CRUD + user balance / group charge / test reset."""

from __future__ import annotations

from telethon import events
from telethon.tl.custom import Message

from app import Kenzo
from app.db.crud.user import update_Money
from app.db.crud.wallets import WalletCRUD
from app.logger import get_logger
from app.telegram.admin.wallets import keyboards, states, texts
from app.telegram.keyboards.admin import Panel_Admin_Buttons, panel_back
from app.telegram.state import clear_user, delete_data, get_data, get_step, set_data, set_step
from config import ADMIN_ID

logger = get_logger(__name__)


def is_number(msg: str) -> bool:
    try:
        float(msg)
        return True
    except ValueError:
        return False


async def get_wallets_menu_text():
    """Get the wallets menu text"""
    wallets = await WalletCRUD().get_all_wallets()
    if not wallets:
        return texts.WALLETS_MENU_EMPTY

    menu_text = texts.WALLETS_MENU_HEADER
    for wallet in wallets:
        menu_text += texts.wallet_menu_line(wallet)
    menu_text += texts.WALLETS_MENU_FOOTER
    return menu_text


async def wallet_message_handler(event: Message):
    msg = event.message.text
    user_id = event.sender_id

    if await get_step(user_id) == states.ADD_WALLET_ADDRESS_STEP and msg:
        wallet_type = await get_data(user_id, "wallet_type")
        if not wallet_type:
            await event.respond(texts.WALLET_TYPE_NOT_FOUND_ERROR)
            await clear_user(user_id)
            await set_step(user_id, states.SETTINGS_CARD_TO_CARD_STEP)
            return

        await set_data(user_id, "wallet_address", msg)
        await set_step(user_id, states.ADD_WALLET_API_KEY_STEP)
        await event.respond(texts.wallet_api_key_prompt(wallet_type))

    elif await get_step(user_id) == states.ADD_WALLET_API_KEY_STEP and msg:
        address = await get_data(user_id, "wallet_address")
        wallet_type = await get_data(user_id, "wallet_type")

        if not address or not wallet_type:
            await event.respond(texts.WALLET_INFO_ERROR)
            await clear_user(user_id)
            await set_step(user_id, states.SETTINGS_CARD_TO_CARD_STEP)
            return

        api_key = msg if msg != "/skip" else None

        if api_key is None and wallet_type.upper() in texts.WALLET_API_KEY_REQUIRED_TYPES:
            await event.respond(texts.wallet_api_key_prompt(wallet_type))
            return

        existing_wallet = await WalletCRUD().get_wallet_by_type(wallet_type)
        if existing_wallet:
            await event.respond(texts.WALLET_DUPLICATE_ERROR_TEMPLATE.format(wallet_type=wallet_type))
            await clear_user(user_id)
            await set_step(user_id, states.SETTINGS_CARD_TO_CARD_STEP)
            return

        wallet = await WalletCRUD().create_wallet(address=address, wallet_type=wallet_type, api_key=api_key)
        await clear_user(user_id)
        await set_step(user_id, states.SETTINGS_CARD_TO_CARD_STEP)
        if wallet:
            await event.respond(texts.WALLET_ADDED_SUCCESS_TEMPLATE.format(wallet_type=wallet_type))
        else:
            await event.respond(texts.WALLET_ADD_FAILED)

    elif await get_step(user_id) == states.EDIT_WALLET_ADDRESS_STEP and msg:
        wallet_id = int(await get_data(user_id, "edit_wallet_id"))
        await set_data(user_id, "edit_wallet_address_value", msg)
        wallet = await WalletCRUD().get_wallet_by_id(wallet_id)

        existing_wallets = await WalletCRUD().get_all_wallets()
        existing_types = {w.type.upper() for w in existing_wallets if w.id != wallet_id}
        current_type = wallet.type.upper()

        await event.respond(
            texts.WALLET_TYPE_SELECT_PROMPT_TEMPLATE.format(current_type=wallet.type),
            buttons=keyboards.edit_wallet_type_buttons(wallet_id, existing_types, current_type),
        )

    elif await get_step(user_id) == states.EDIT_WALLET_API_KEY_STEP and msg:
        wallet_id = int(await get_data(user_id, "edit_wallet_id"))
        address = await get_data(user_id, "edit_wallet_address_value")
        wallet_type = await get_data(user_id, "edit_wallet_type_value")

        if not address or not wallet_type:
            await event.respond(texts.WALLET_INFO_ERROR)
            await clear_user(user_id)
            await set_step(user_id, states.SETTINGS_CARD_TO_CARD_STEP)
            return

        existing_wallet = await WalletCRUD().get_wallet_by_type(wallet_type)
        if existing_wallet and existing_wallet.id != wallet_id:
            await event.respond(texts.WALLET_TYPE_CHANGE_BLOCKED_TEMPLATE.format(wallet_type=wallet_type))
            await clear_user(user_id)
            await set_step(user_id, states.SETTINGS_CARD_TO_CARD_STEP)
            return

        api_key = msg if msg != "/skip" else None
        if api_key is None and wallet_type.upper() in texts.WALLET_API_KEY_REQUIRED_TYPES:
            current = await WalletCRUD().get_wallet_by_id(wallet_id)
            if not current or not (current.api_key or "").strip():
                await event.respond(
                    texts.wallet_api_key_prompt(wallet_type, api_key_status=texts.WALLET_API_NOT_CONFIGURED)
                )
                return

        wallet = await WalletCRUD().update_wallet(wallet_id, address=address, wallet_type=wallet_type, api_key=api_key)
        await clear_user(user_id)
        await set_step(user_id, states.SETTINGS_CARD_TO_CARD_STEP)
        if wallet:
            await event.respond(texts.WALLET_UPDATED_SUCCESS_TEMPLATE.format(wallet_type=wallet_type))
        else:
            await event.respond(texts.WALLET_UPDATE_FAILED)

    elif await get_step(user_id) == states.DELETE_WALLET_SELECT_STEP and msg.isdigit():
        wallet_id = int(msg)
        wallet = await WalletCRUD().delete_wallet(wallet_id)
        await clear_user(user_id)
        await set_step(user_id, states.SETTINGS_CARD_TO_CARD_STEP)
        if wallet:
            await event.respond(texts.WALLET_DELETED_SUCCESS)
        else:
            await event.respond(texts.WALLET_DELETE_FAILED)


async def _wallet_message_filter(event: Message) -> bool:
    if event.sender_id not in ADMIN_ID:
        return False
    step = await get_step(event.sender_id)
    return step in (
        states.ADD_WALLET_ADDRESS_STEP,
        states.ADD_WALLET_API_KEY_STEP,
        states.EDIT_WALLET_ADDRESS_STEP,
        states.EDIT_WALLET_API_KEY_STEP,
        states.DELETE_WALLET_SELECT_STEP,
    )


async def _balance_admin_message_filter(event: Message) -> bool:
    if event.sender_id not in ADMIN_ID:
        return False
    msg = (event.message.text or "").strip()
    if msg in states.BALANCE_MENU_MESSAGES:
        return True
    return await get_step(event.sender_id) in states.BALANCE_ADMIN_STEPS


async def balance_message_handler(event: Message):
    msg = (event.message.text or "").strip()
    user_id = event.sender_id
    step = await get_step(user_id)

    if msg == "➕ افزودن موجودی":
        await Kenzo.send_message(entity=user_id, message=texts.ADD_BALANCE_USER_ID_PROMPT, buttons=panel_back)
        await set_step(user_id, "addMoney")
        raise events.StopPropagation

    if step == "addMoney":
        await set_data(user_id, "amount_username", msg)
        await set_step(user_id, "amount_username")
        await Kenzo.send_message(entity=user_id, message=texts.ADD_BALANCE_AMOUNT_PROMPT, buttons=panel_back)
        raise events.StopPropagation

    if step == "amount_username":
        username = await get_data(user_id, "amount_username")
        if not is_number(msg):
            logger.info("مقدار وارد شده صحیح نیست")
            raise events.StopPropagation

        await set_step(user_id, "panel")
        new_amount = await update_Money(user_id=username, Money=int(msg))
        amount = int(msg)
        await Kenzo.send_message(
            entity=user_id,
            message=texts.balance_added_admin_message(username, amount, new_amount),
            buttons=Panel_Admin_Buttons,
        )
        await Kenzo.send_message(
            entity=int(username),
            message=texts.balance_added_user_message(username, amount, new_amount),
            buttons=[keyboards.user_new_balance_button(new_amount)],
        )
        await clear_user(user_id)
        raise events.StopPropagation

    if msg == "➖ کسر موجودی":
        await Kenzo.send_message(entity=user_id, message=texts.ADD_BALANCE_USER_ID_PROMPT, buttons=panel_back)
        await set_step(user_id, "KasrMoney")
        raise events.StopPropagation

    if step == "KasrMoney":
        await set_data(user_id, "amount_username", msg)
        await set_step(user_id, "Kasr_amount_username")
        await Kenzo.send_message(entity=user_id, message=texts.DEDUCT_BALANCE_AMOUNT_PROMPT, buttons=panel_back)
        raise events.StopPropagation

    if step == "Kasr_amount_username":
        username = await get_data(user_id, "amount_username")
        if not is_number(msg):
            logger.info("مقدار وارد شده صحیح نیست")
            raise events.StopPropagation

        new_amount = await update_Money(user_id=username, Money=-int(msg))
        amount = int(msg)
        await Kenzo.send_message(
            entity=user_id,
            message=texts.balance_deducted_admin_message(username, amount, new_amount),
            buttons=Panel_Admin_Buttons,
        )
        await Kenzo.send_message(
            entity=int(username),
            message=texts.balance_deducted_user_message(username, amount, new_amount),
            buttons=[keyboards.user_new_balance_button(new_amount)],
        )
        await set_step(user_id, "panel")
        await clear_user(user_id)
        raise events.StopPropagation

    if msg == "💰 شارژ گروهی":
        await Kenzo.send_message(
            entity=user_id,
            message=texts.GROUP_CHARGE_MENU_TEXT,
            buttons=keyboards.group_charge_menu_buttons(),
        )
        raise events.StopPropagation

    if step == states.GROUP_CHARGE_AMOUNT_STEP:
        charge_type = await get_data(user_id, "group_charge_type")
        if not is_number(msg):
            await Kenzo.send_message(
                entity=user_id,
                message=texts.GROUP_CHARGE_INVALID_NUMBER,
                buttons=panel_back,
            )
            raise events.StopPropagation

        amount = int(msg)
        if amount <= 0:
            await Kenzo.send_message(
                entity=user_id,
                message=texts.GROUP_CHARGE_INVALID_AMOUNT,
                buttons=panel_back,
            )
            raise events.StopPropagation

        await set_data(user_id, "group_charge_amount_value", str(amount))
        user_type_text = texts.ALL_USERS_LABEL if charge_type == "all" else texts.ACTIVE_SERVICE_USERS_LABEL
        await Kenzo.send_message(
            entity=user_id,
            message=texts.group_charge_confirmation(user_type_text, amount),
            buttons=keyboards.group_charge_confirm_buttons(charge_type, amount),
        )
        await set_step(user_id, "panel")
        await delete_data(user_id, "group_charge_type")
        await delete_data(user_id, "group_charge_amount_value")
        raise events.StopPropagation

    if msg == "🔄 ریست دریافت تست":
        await Kenzo.send_message(
            entity=user_id,
            message=texts.GROUP_RESET_MENU_TEXT,
            buttons=keyboards.group_reset_menu_buttons(),
        )
        raise events.StopPropagation


def register(client):
    client.add_event_handler(
        wallet_message_handler,
        events.NewMessage(incoming=True, from_users=ADMIN_ID, func=_wallet_message_filter),
    )
    client.add_event_handler(
        balance_message_handler,
        events.NewMessage(incoming=True, from_users=ADMIN_ID, func=_balance_admin_message_filter),
    )
