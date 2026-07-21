"""Callback handlers for admin settings_payment."""

import time

from telethon import events

from app import Kenzo
from app.db.crud.cards import ManualCardManager
from app.db.crud.manual_auto_approve_rules import ManualAutoApproveRuleCRUD, build_manual_card_log_caption
from app.db.crud.settings import SettingsManager
from app.db.crud.transactions import TransactionCRUD
from app.db.crud.user import UserCRUD, get_Money
from app.services.billing.direct_pay_fulfillment import (
    cancel_after_manual_reject,
    try_fulfill_after_manual_credit,
)
from app.telegram.admin.settings_payment import keyboards, texts
from app.telegram.state import set_data, set_step
from config import ADMIN_ID

_maar_crud = ManualAutoApproveRuleCRUD()

_SETTINGS_PAYMENT_EXACT_CALLBACKS = frozenset(
    {
        "add_manual_card",
        "select_active_card",
        "delete_manual_card",
        "toggle_manual_auto_confirm",
        "toggle_manual_card_random_mode",
        "toggle_manual_card_visibility",
        "maar_rules_menu",
        "maar_add",
        "set_manual_limits",
        "set_crypto_limits",
        "set_reseller_min_wallet",
        "bonus_settings_menu",
        "toggle_manual_bonus",
        "toggle_crypto_bonus",
        "set_manual_bonus_percent",
        "set_crypto_bonus_percent",
    }
)

_SETTINGS_PAYMENT_PREFIXES = (
    "set_active_card:",
    "remove_card:",
    "maar_view:",
    "maar_toggle:",
    "maar_delete:",
    "maar_up:",
    "maar_down:",
    "maar_edit_min:",
    "maar_edit_max:",
    "maar_edit_delay:",
    "BackTOSettingsCardToCard",
)


async def _refresh_gateway_settings_view(event, settings=None) -> None:
    if settings is None:
        settings = await SettingsManager().get_settings()
    cards = await ManualCardManager().get_all_cards()
    active = next((c for c in cards if c.active), None)
    random_mode_status = texts.RANDOM_MODE_ACTIVE if settings.manual_card_random_mode else texts.RANDOM_MODE_INACTIVE
    await event.edit(
        texts.gateway_settings_back_message(active, random_mode_status, settings),
        buttons=keyboards.gateway_settings_buttons(settings),
    )


async def _maar_menu():
    settings = await SettingsManager().get_settings()
    master = "✅" if settings and settings.manual_auto_confirm else "❌"
    rules = await _maar_crud.get_all()
    lines = [texts.maar_menu_header(master)]
    for index, rule in enumerate(rules, 1):
        status = "✅" if rule.is_active else "❌"
        lines.append(f"\n{index}. {status} `{texts.maar_range(rule)}` → {texts.maar_delay(rule)}")
    if not rules:
        lines.append(texts.MAAR_NO_RULES)
    return "".join(lines), keyboards.maar_menu_buttons(rules)


async def _maar_show_rule(event, rule_id: int):
    rule = await _maar_crud.get(rule_id)
    if not rule:
        await event.answer(texts.MAAR_NOT_FOUND, alert=True)
        return
    rules = await _maar_crud.get_all()
    await event.edit(
        texts.maar_rule_detail(rule_id, rule),
        buttons=keyboards.maar_show_rule_buttons(rule_id, rules),
    )


def _settings_payment_callback_filter(event: events.CallbackQuery.Event) -> bool:
    if event.sender_id not in ADMIN_ID:
        return False
    data = event.data.decode("utf-8")
    if data in _SETTINGS_PAYMENT_EXACT_CALLBACKS:
        return True
    return data.startswith(_SETTINGS_PAYMENT_PREFIXES)


def _transaction_review_callback_filter(event: events.CallbackQuery.Event) -> bool:
    if event.sender_id not in ADMIN_ID:
        return False
    data = event.data.decode("utf-8")
    return data.startswith("confirm_transaction") or data.startswith("reject_transaction")


async def callback_settings_payment(event: events.CallbackQuery.Event):
    data = event.data.decode("UTF-8")
    if data == "add_manual_card":
        await set_step(event.sender_id, "add_card_number")
        await event.edit(
            texts.ADD_CARD_NUMBER_PROMPT,
            buttons=keyboards.back_to_settings_card_row(),
        )

    elif data == "select_active_card":
        cards = await ManualCardManager().get_all_cards()
        if cards:
            await event.edit(
                texts.SELECT_ACTIVE_CARD_PROMPT,
                buttons=keyboards.card_list_buttons(cards, "set_active_card", active_marker=True),
            )
        else:
            await event.edit(texts.NO_CARDS_REGISTERED, buttons=keyboards.back_to_settings_card_row())

    elif data.startswith("set_active_card:"):
        card_id = int(data.split(":")[1])
        await ManualCardManager().set_active(card_id)
        await event.edit(texts.ACTIVE_CARD_UPDATED, buttons=keyboards.back_to_settings_card_row())

    elif data == "delete_manual_card":
        cards = await ManualCardManager().get_all_cards()
        if cards:
            await event.edit(
                texts.DELETE_CARD_PROMPT,
                buttons=keyboards.card_list_buttons(cards, "remove_card"),
            )
        else:
            await event.edit(texts.NO_CARDS_REGISTERED, buttons=keyboards.back_to_settings_card_row())

    elif data.startswith("remove_card:"):
        card_id = int(data.split(":")[1])
        await ManualCardManager().delete_card(card_id)
        await event.edit(texts.CARD_DELETED, buttons=keyboards.back_to_settings_card_row())

    elif data == "toggle_manual_auto_confirm":
        settings = await SettingsManager().get_settings()
        new_status = not settings.manual_auto_confirm
        await SettingsManager().update_setting(settings.id, manual_auto_confirm=new_status)
        settings = await SettingsManager().get_settings()
        await _refresh_gateway_settings_view(event, settings)

    elif data == "toggle_manual_card_random_mode":
        settings = await SettingsManager().get_settings()
        new_status = not settings.manual_card_random_mode
        await SettingsManager().update_setting(settings.id, manual_card_random_mode=new_status)
        settings = await SettingsManager().get_settings()
        await _refresh_gateway_settings_view(event, settings)

    elif data == "toggle_manual_card_visibility":
        settings = await SettingsManager().get_settings()
        new_mode = texts.next_manual_card_visibility_mode(settings)
        await SettingsManager().update_setting(
            settings.id,
            manual_card_visibility=new_mode,
            pay_mode=True,
        )
        settings = await SettingsManager().get_settings()
        await _refresh_gateway_settings_view(event, settings)

    elif data == "maar_rules_menu":
        menu_text, buttons = await _maar_menu()
        await event.edit(menu_text, buttons=buttons)
    elif data == "maar_add":
        await set_step(event.sender_id, "maar_add_min")
        await event.edit(texts.MAAR_ADD_MIN_PROMPT, buttons=keyboards.maar_add_back_button())
    elif data.startswith("maar_view:"):
        await _maar_show_rule(event, int(data.split(":")[1]))
    elif data.startswith("maar_toggle:"):
        rule_id = int(data.split(":")[1])
        rule = await _maar_crud.get(rule_id)
        if rule:
            await _maar_crud.update(rule_id, is_active=not rule.is_active)
        await _maar_show_rule(event, rule_id)
    elif data.startswith("maar_delete:"):
        await _maar_crud.delete(int(data.split(":")[1]))
        await _maar_crud.renumber_sort_orders()
        menu_text, buttons = await _maar_menu()
        await event.edit(menu_text, buttons=buttons)
    elif data.startswith("maar_up:") or data.startswith("maar_down:"):
        rule_id = int(data.split(":")[1])
        rules = await _maar_crud.get_all()
        idx = next(i for i, rule in enumerate(rules) if rule.id == rule_id)
        swap_index = idx - 1 if data.startswith("maar_up:") else idx + 1
        if 0 <= swap_index < len(rules):
            await _maar_crud.swap_sort_order(rule_id, rules[swap_index].id)
        await _maar_show_rule(event, rule_id)
    elif data.startswith("maar_edit_min:") or data.startswith("maar_edit_max:") or data.startswith("maar_edit_delay:"):
        rule_id = int(data.split(":")[1])
        step = data.rsplit(":", 1)[0]
        await set_data(event.sender_id, "maar_rule_id", rule_id)
        await set_step(event.sender_id, step)
        await event.edit(texts.MAAR_EDIT_VALUE_PROMPT, buttons=keyboards.maar_edit_back_button(rule_id))

    elif data == "set_manual_limits":
        await set_step(event.sender_id, "set_manual_min")
        await event.edit(texts.MANUAL_MIN_PROMPT, buttons=keyboards.back_to_settings_card_row())

    elif data == "set_crypto_limits":
        await set_step(event.sender_id, "set_crypto_min")
        await event.edit(texts.CRYPTO_MIN_PROMPT, buttons=keyboards.back_to_settings_card_row())
        return

    elif data == "set_reseller_min_wallet":
        settings = await SettingsManager().get_settings()
        current = int(settings.reseller_min_wallet_balance or 0)
        await set_step(event.sender_id, "set_reseller_min_wallet")
        await event.edit(
            f"{texts.RESELLER_MIN_WALLET_PROMPT}\n\nمقدار فعلی: `{current:,}` تومان",
            buttons=keyboards.back_to_settings_card_row(),
        )

    elif data == "bonus_settings_menu":
        settings = await SettingsManager().get_settings()
        bonus_text, buttons = await keyboards.get_bonus_settings_menu(settings)
        await event.edit(bonus_text, buttons=buttons)

    elif data == "toggle_manual_bonus":
        settings = await SettingsManager().get_settings()
        new_status = not settings.manual_bonus_enabled
        await SettingsManager().update_setting(settings.id, manual_bonus_enabled=new_status)
        settings = await SettingsManager().get_settings()
        bonus_text, buttons = await keyboards.get_bonus_settings_menu(settings)
        await event.edit(bonus_text, buttons=buttons)

    elif data == "toggle_crypto_bonus":
        settings = await SettingsManager().get_settings()
        new_status = not settings.crypto_bonus_enabled
        await SettingsManager().update_setting(settings.id, crypto_bonus_enabled=new_status)
        settings = await SettingsManager().get_settings()
        bonus_text, buttons = await keyboards.get_bonus_settings_menu(settings)
        await event.edit(bonus_text, buttons=buttons)

    elif data == "set_manual_bonus_percent":
        await set_step(event.sender_id, "set_manual_bonus_percent")
        await event.edit(texts.MANUAL_BONUS_PERCENT_PROMPT, buttons=keyboards.back_to_bonus_menu_button())

    elif data == "set_crypto_bonus_percent":
        await set_step(event.sender_id, "set_crypto_bonus_percent")
        await event.edit(texts.CRYPTO_BONUS_PERCENT_PROMPT, buttons=keyboards.back_to_bonus_menu_button())

    elif data.startswith("BackTOSettingsCardToCard"):
        await set_step(user_id=event.sender_id, step="SettingsCardToCard")
        settings = await SettingsManager().get_settings()
        await _refresh_gateway_settings_view(event, settings)


async def callback_transaction_review(event: events.CallbackQuery.Event):
    data = event.data.decode("utf-8")

    if data.startswith("confirm_transaction"):
        tx_id = int(data.split(":")[1])
        tx = await TransactionCRUD().get(tx_id)
        if not tx or tx.status != "pending":
            await event.answer(texts.TX_ALREADY_REVIEWED, alert=True)
            raise events.StopPropagation
        reduser = await UserCRUD().read_user(user_id=tx.user_id)
        settings = await SettingsManager().get_settings()
        result = await TransactionCRUD().approve_manual(tx)
        if not result:
            await event.answer(texts.TX_ALREADY_REVIEWED, alert=True)
            raise events.StopPropagation
        admin_message = await build_manual_card_log_caption(
            user_id=tx.user_id,
            amount=int(tx.amount),
            header=texts.TX_APPROVED_ADMIN_HEADER,
            reduser=reduser,
            new_balance=result["new_balance"],
            bonus=result["bonus"],
            total=result["total"],
            bonus_percent=settings.manual_bonus_percent,
            created_at=tx.created_at,
            completed_at=result["completed_at"],
        )
        await event.edit(admin_message, buttons=keyboards.tx_review_result_button(approved=True))
        fulfilled = await try_fulfill_after_manual_credit(tx_id)
        if not fulfilled:
            await Kenzo.send_message(
                entity=int(tx.user_id),
                message=texts.tx_approved_user_message(
                    tx.user_id,
                    int(tx.amount),
                    result["bonus"],
                    settings.manual_bonus_percent,
                    result["total"],
                ),
                buttons=keyboards.no_action_balance_button(result["new_balance"]),
            )

    elif data.startswith("reject_transaction"):
        tx_id = int(data.split(":")[1])
        tx = await TransactionCRUD().get(tx_id)
        if not tx or tx.status != "pending":
            await event.answer(texts.TX_ALREADY_REVIEWED, alert=True)
            raise events.StopPropagation
        reduser = await UserCRUD().read_user(user_id=tx.user_id)
        await ManualAutoApproveRuleCRUD.cancel_schedule(tx_id)
        completed_at = int(time.time())
        await TransactionCRUD().update(tx_id, status="rejected", completed_at=completed_at)
        await cancel_after_manual_reject(tx_id)
        admin_message = await build_manual_card_log_caption(
            user_id=tx.user_id,
            amount=int(tx.amount),
            header=texts.TX_REJECTED_ADMIN_HEADER,
            reduser=reduser,
            created_at=tx.created_at,
            completed_at=completed_at,
        )
        await event.edit(admin_message, buttons=keyboards.tx_review_result_button(approved=False))
        await Kenzo.send_message(
            entity=int(tx.user_id),
            message=f"{texts.TX_REJECT_USER_MESSAGE}\nمبلغ: `{int(tx.amount):,}` تومان",
            buttons=keyboards.tx_reject_user_balance_button(await get_Money(tx.user_id)),
        )

    raise events.StopPropagation


def register(client):
    client.add_event_handler(
        callback_settings_payment,
        events.CallbackQuery(func=_settings_payment_callback_filter),
    )
    client.add_event_handler(
        callback_transaction_review,
        events.CallbackQuery(func=_transaction_review_callback_filter),
    )
