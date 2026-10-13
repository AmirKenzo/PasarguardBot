"""Callback handlers for admin wallets."""

from telethon import events

from app.db.crud.services import ServiceCRUD
from app.db.crud.user import UserCRUD
from app.db.crud.wallets import WalletCRUD
from app.logger import LogType, get_logger
from app.telegram.admin.wallets import keyboards, states, texts
from app.telegram.admin.wallets.messages import get_wallets_menu_text
from app.telegram.keyboards.admin import Panel_Admin_Buttons
from app.telegram.shared.utils.logging import send_log_message
from app.telegram.state import clear_user, delete_data, get_data, set_data, set_step
from config import ADMIN_ID

logger = get_logger(__name__)


def wallet_callback_filter(event: events.CallbackQuery.Event) -> bool:
    if event.sender_id not in ADMIN_ID:
        return False
    data = event.data.decode("UTF-8")
    if data in (
        states.WALLET_MANAGEMENT_CALLBACK,
        "add_wallet",
        "list_wallets",
        "edit_wallet_menu",
        "delete_wallet_menu",
    ):
        return True
    return data.startswith(("select_wallet_type:", "edit_wallet:", "edit_select_wallet_type:", "delete_wallet:"))


async def wallet_callback_handler(event: events.CallbackQuery.Event):
    data = event.data.decode("UTF-8")

    if data == states.WALLET_MANAGEMENT_CALLBACK:
        text = await get_wallets_menu_text()
        buttons = await keyboards.wallets_menu_buttons()
        await event.edit(text, buttons=buttons)

    elif data == "add_wallet":
        existing_wallets = await WalletCRUD().get_all_wallets()
        existing_types = {w.type.upper() for w in existing_wallets}

        buttons = keyboards.wallet_type_buttons(existing_types)

        if not buttons:
            await event.edit(
                texts.WALLET_ALL_TYPES_EXIST,
                buttons=keyboards.wallet_management_back_button(),
            )
        else:
            buttons.extend(keyboards.wallet_management_back_button())
            await event.edit(texts.WALLET_TYPE_SELECT_PROMPT, buttons=buttons)

    elif data.startswith("select_wallet_type:"):
        wallet_type = data.split(":")[1]
        await set_data(event.sender_id, "wallet_type", wallet_type)
        await set_step(event.sender_id, states.ADD_WALLET_ADDRESS_STEP)
        await event.edit(
            texts.WALLET_ADDRESS_PROMPT_TEMPLATE.format(wallet_type=wallet_type),
            buttons=keyboards.wallet_management_back_button(),
        )

    elif data == "list_wallets":
        wallets = await WalletCRUD().get_all_wallets()
        if wallets:
            text = texts.WALLET_LIST_HEADER
            for wallet in wallets:
                text += texts.wallet_list_entry(wallet)
        else:
            text = texts.WALLET_LIST_EMPTY
        await event.edit(text, buttons=keyboards.wallet_management_back_button())

    elif data == "edit_wallet_menu":
        wallets = await WalletCRUD().get_all_wallets()
        if wallets:
            await event.edit(
                texts.WALLET_EDIT_SELECT_PROMPT,
                buttons=keyboards.wallet_action_list_buttons(wallets, "edit_wallet"),
            )
        else:
            await event.edit(texts.WALLET_LIST_EMPTY, buttons=keyboards.wallet_management_back_button())

    elif data.startswith("edit_wallet:"):
        wallet_id = int(data.split(":")[1])
        wallet = await WalletCRUD().get_wallet_by_id(wallet_id)
        if wallet:
            await set_data(event.sender_id, "edit_wallet_id", str(wallet_id))
            await set_step(event.sender_id, states.EDIT_WALLET_ADDRESS_STEP)
            await event.edit(texts.wallet_edit_text(wallet), buttons=keyboards.wallet_management_back_button())
        else:
            await event.edit(texts.WALLET_NOT_FOUND, buttons=keyboards.wallet_management_back_button())

    elif data.startswith("edit_select_wallet_type:"):
        parts = data.split(":")
        wallet_id = int(parts[1])
        wallet_type = parts[2]
        address = await get_data(event.sender_id, "edit_wallet_address_value")

        if not address:
            await event.respond(texts.WALLET_INFO_ERROR)
            await clear_user(event.sender_id)
            await set_step(event.sender_id, states.SETTINGS_CARD_TO_CARD_STEP)
            return

        await set_data(event.sender_id, "edit_wallet_type_value", wallet_type)
        await set_step(event.sender_id, states.EDIT_WALLET_API_KEY_STEP)
        wallet = await WalletCRUD().get_wallet_by_id(wallet_id)
        api_key_status = texts.WALLET_API_CONFIGURED if wallet.api_key else texts.WALLET_API_NOT_CONFIGURED
        await event.edit(
            texts.wallet_api_key_prompt(wallet_type, api_key_status=api_key_status),
            buttons=keyboards.wallet_management_back_button(),
        )

    elif data == "delete_wallet_menu":
        wallets = await WalletCRUD().get_all_wallets()
        if wallets:
            await event.edit(
                texts.WALLET_DELETE_SELECT_PROMPT,
                buttons=keyboards.wallet_action_list_buttons(wallets, "delete_wallet"),
            )
        else:
            await event.edit(texts.WALLET_LIST_EMPTY, buttons=keyboards.wallet_management_back_button())

    elif data.startswith("delete_wallet:"):
        wallet_id = int(data.split(":")[1])
        wallet = await WalletCRUD().get_wallet_by_id(wallet_id)
        if wallet:
            await WalletCRUD().delete_wallet(wallet_id)
            text = await get_wallets_menu_text()
            buttons = await keyboards.wallets_menu_buttons()
            await event.edit(
                texts.WALLET_DELETED_INLINE_TEMPLATE.format(wallet_type=wallet.type) + text, buttons=buttons
            )
        else:
            await event.edit(texts.WALLET_NOT_FOUND, buttons=keyboards.wallet_management_back_button())

    raise events.StopPropagation


def balance_callback_filter(event: events.CallbackQuery.Event) -> bool:
    if event.sender_id not in ADMIN_ID:
        return False
    data = event.data.decode("utf-8")
    if data in ("group_charge_cancel", "group_reset_cancel"):
        return True
    return data.startswith(("group_charge:", "group_charge_confirm:", "group_reset:", "group_reset_confirm:"))


async def balance_callback_handler(event: events.CallbackQuery.Event):
    data = event.data.decode("utf-8")

    if data.startswith("group_charge:"):
        charge_type = data.split(":")[1]
        await set_data(event.sender_id, "group_charge_type", charge_type)
        await set_step(event.sender_id, states.GROUP_CHARGE_AMOUNT_STEP)
        user_type_text = texts.ALL_USERS_LABEL if charge_type == "all" else texts.ACTIVE_SERVICE_USERS_LABEL
        await event.edit(
            texts.group_charge_amount_prompt(user_type_text),
            buttons=keyboards.group_charge_back_button(),
        )
        raise events.StopPropagation

    if data == "group_charge_cancel":
        await delete_data(event.sender_id, "group_charge_type")
        await delete_data(event.sender_id, "group_charge_amount_value")
        await set_step(event.sender_id, "panel")
        await event.edit(texts.GROUP_CHARGE_CANCELLED, buttons=Panel_Admin_Buttons)
        raise events.StopPropagation

    if data.startswith("group_charge_confirm:"):
        parts = data.split(":")
        if len(parts) != 3:
            await event.answer("❌ خطا در پردازش درخواست", alert=True)
            raise events.StopPropagation from None

        charge_type = parts[1]
        try:
            amount = int(parts[2])
        except ValueError:
            await event.answer("❌ مبلغ نامعتبر است", alert=True)
            raise events.StopPropagation from None

        target_ids: list[int] | None
        if charge_type == "all":
            target_ids = None
            target_count = await UserCRUD().count_all_users()
            user_type_text = texts.ALL_USERS_LABEL
        else:
            user_ids = await ServiceCRUD().get_unique_user_ids()
            if isinstance(user_ids, str):
                await event.edit(
                    texts.group_charge_users_error(user_ids),
                    buttons=Panel_Admin_Buttons,
                )
                raise events.StopPropagation from None

            target_ids = sorted({int(uid) for uid in user_ids if uid})
            target_count = len(target_ids)
            user_type_text = texts.ACTIVE_SERVICE_USERS_LABEL

        if not target_count:
            await event.edit(texts.GROUP_CHARGE_NO_USERS, buttons=Panel_Admin_Buttons)
            raise events.StopPropagation from None

        await event.edit(
            texts.group_charge_processing(user_type_text, target_count, amount),
            buttons=None,
        )

        try:
            success_count = await UserCRUD().add_balance_bulk(amount, target_ids)
            failed_count = 0
        except Exception as exc:
            logger.error("Error group charging %s users: %s", target_count, exc)
            success_count = 0
            failed_count = target_count

        if not success_count and not failed_count:
            await event.edit(texts.GROUP_CHARGE_NO_USERS, buttons=Panel_Admin_Buttons)
            await set_step(event.sender_id, "panel")
            raise events.StopPropagation from None

        total_users = success_count + failed_count
        total_charged = success_count * amount
        await event.edit(
            texts.group_charge_result(user_type_text, total_users, success_count, failed_count, amount, total_charged),
            buttons=Panel_Admin_Buttons,
        )
        await send_log_message(
            LogType.OTHER,
            message=texts.group_charge_log_message(
                event.sender_id, user_type_text, total_users, success_count, failed_count, amount, total_charged
            ),
        )
        await set_step(event.sender_id, "panel")
        raise events.StopPropagation

    if data.startswith("group_reset:"):
        reset_type = data.split(":")[1]
        tested_users = await UserCRUD().get_users_with_tested()
        if not tested_users:
            await event.edit(texts.NO_TESTED_USERS, buttons=Panel_Admin_Buttons)
            raise events.StopPropagation from None

        if reset_type == "all":
            users_to_reset = tested_users
            user_type_text = texts.ALL_USERS_LABEL
        else:
            user_ids = await ServiceCRUD().get_unique_user_ids()
            if isinstance(user_ids, str):
                await event.edit(
                    texts.group_reset_users_error(user_ids),
                    buttons=Panel_Admin_Buttons,
                )
                raise events.StopPropagation from None

            user_ids_set = set(user_ids)
            users_to_reset = [user for user in tested_users if user.id in user_ids_set]
            user_type_text = texts.ACTIVE_SERVICE_USERS_LABEL

        if not users_to_reset:
            await event.edit(texts.NO_TESTED_ACTIVE_USERS, buttons=Panel_Admin_Buttons)
            raise events.StopPropagation from None

        await event.edit(
            texts.group_reset_confirmation(user_type_text, len(tested_users), len(users_to_reset)),
            buttons=keyboards.group_reset_confirm_buttons(reset_type),
        )
        raise events.StopPropagation

    if data == "group_reset_cancel":
        await set_step(event.sender_id, "panel")
        await event.edit(texts.GROUP_RESET_CANCELLED, buttons=Panel_Admin_Buttons)
        raise events.StopPropagation

    if data.startswith("group_reset_confirm:"):
        parts = data.split(":")
        if len(parts) != 2:
            await event.answer("❌ خطا در پردازش درخواست", alert=True)
            raise events.StopPropagation from None

        reset_type = parts[1]
        tested_users = await UserCRUD().get_users_with_tested()
        if not tested_users:
            await event.edit(texts.NO_TESTED_USERS, buttons=Panel_Admin_Buttons)
            raise events.StopPropagation from None

        if reset_type == "all":
            users_to_reset = tested_users
            user_type_text = texts.ALL_USERS_LABEL
        else:
            user_ids = await ServiceCRUD().get_unique_user_ids()
            if isinstance(user_ids, str):
                await event.edit(
                    texts.group_reset_users_error(user_ids),
                    buttons=Panel_Admin_Buttons,
                )
                raise events.StopPropagation from None

            user_ids_set = set(user_ids)
            users_to_reset = [user for user in tested_users if user.id in user_ids_set]
            user_type_text = texts.ACTIVE_SERVICE_USERS_LABEL

        if not users_to_reset:
            await event.edit(texts.NO_TESTED_ACTIVE_USERS, buttons=Panel_Admin_Buttons)
            raise events.StopPropagation from None

        await event.edit(
            texts.group_reset_processing(user_type_text, len(tested_users), len(users_to_reset)),
            buttons=None,
        )

        success_count = 0
        failed_count = 0
        for user in users_to_reset:
            try:
                result = await UserCRUD().update_user(user.id, tested=False)
                if result:
                    success_count += 1
                else:
                    failed_count += 1
            except Exception as exc:
                logger.error("Error resetting tested field for user %s: %s", user.id, exc)
                failed_count += 1

        await event.edit(
            texts.group_reset_result(
                user_type_text, len(tested_users), len(users_to_reset), success_count, failed_count
            ),
            buttons=Panel_Admin_Buttons,
        )
        await send_log_message(
            LogType.OTHER,
            message=texts.group_reset_log_message(
                event.sender_id,
                user_type_text,
                len(tested_users),
                len(users_to_reset),
                success_count,
                failed_count,
            ),
        )
        await set_step(event.sender_id, "panel")
        raise events.StopPropagation

    raise events.StopPropagation


def register(client):
    client.add_event_handler(wallet_callback_handler, events.CallbackQuery(func=wallet_callback_filter))
    client.add_event_handler(balance_callback_handler, events.CallbackQuery(func=balance_callback_filter))
