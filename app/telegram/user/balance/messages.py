"""Message handlers for user balance."""

import asyncio
import contextlib
import os
import random
from decimal import Decimal
from io import BytesIO

import qrcode
from PIL import Image
from telethon import Button, events
from telethon.tl.custom import Message

from app import Kenzo
from app.db.crud.cards import ManualCardManager
from app.db.crud.cryptopayments import (
    CryptoPaymentsCRUD,
    add_order_crypto_payment,
    allocate_order_id,
    count_pending_orders,
    set_order_msg_id,
)
from app.db.crud.keyboards import get_button_text
from app.db.crud.log_channels import LogChannelManager
from app.db.crud.manual_auto_approve_rules import ManualAutoApproveRuleCRUD
from app.db.crud.receipt_hash import ReceiptHashCRUD, compute_receipt_phash
from app.db.crud.settings import SettingsManager
from app.db.crud.transactions import TransactionCRUD
from app.db.crud.user import UserCRUD
from app.db.crud.wallets import WalletCRUD
from app.logger import LogType, get_logger
from app.services.billing.direct_pay_flow import (
    DIRECT_PAY_RENEW_TOPUP_INTRO_DEFAULT,
    DIRECT_PAY_TOPUP_INTRO_DEFAULT,
    REDIS_DIRECT_PAY_ACTIVE,
    REDIS_MABLAGH,
    fill_placeholders,
    is_direct_pay_active,
)
from app.services.billing.direct_pay_store import (
    ACTIVE_STATUSES,
    KIND_RENEW,
    cancel_pending_for_user,
    get_pending_for_user,
    link_crypto_order,
    link_transaction,
)
from app.services.pricing.crypto_amounts import (
    calculate_pol_amount_with_tax,
    calculate_ton_amount_with_tax,
    calculate_trx_amount_with_tax,
    calculate_usdt_amount_with_tax,
)
from app.telegram.keyboards.balance import balance_flow_cancel_rows, create_inline_cartbcard
from app.telegram.keyboards.common import is_keyboard_config_step
from app.telegram.keyboards.home import bhome_buttons
from app.telegram.shared.guards.callback_guards import notify_session_expired
from app.telegram.shared.guards.channel_gate import ensure_channel_membership, extract_start_param
from app.telegram.shared.utils.logging import send_log_message
from app.telegram.shared.utils.maintenance import bot_is_offline
from app.telegram.state import clear_user, get_data, get_step, set_data, set_step
from app.telegram.user.balance import keyboards, states, texts
from app.telegram.user.payment import send_star_invoice
from app.utils.formatting.dates import Time_Date
from app.utils.text.bot_texts import get_bot_text
from config import LOG_CHANNEL

logger = get_logger(__name__)

# Wallet types and on-chain metadata for the two extra USDT networks and POL.
USDT_TON = "USDT-TON"
USDT_BEP20 = "USDT-BEP20"
USDT_TON_JETTON = "EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs"
USDT_BEP20_CONTRACT = "0x55d398326f99059fF775485246999027B3197955"


async def build_manual_card_line(settings) -> str:
    cards = await ManualCardManager().get_all_cards()
    if settings.manual_card_random_mode and cards:
        selected_card = random.choice(cards)
        return f"`{selected_card.number}`\n👤  {selected_card.name}"
    active = next((c for c in cards if c.active), None)
    if active:
        return f"`{active.number}`\n👤  {active.name}"
    return texts.NO_CARD_REGISTERED


def manual_card_limit_placeholders(settings) -> dict[str, str]:
    return {
        "min_amount": f"{settings.manual_deposit_min:,}",
        "max_amount": f"{settings.manual_deposit_max:,}",
    }


def deposit_limit_placeholders(min_amount: int, max_amount: int) -> dict[str, str]:
    return {
        "min_amount": f"{min_amount:,}",
        "max_amount": f"{max_amount:,}",
    }


async def respond_deposit_amount_range_error(
    event,
    *,
    text_key: str,
    default: str,
    min_amount: int,
    max_amount: int,
    lang: str = "fa",
) -> None:
    placeholders = deposit_limit_placeholders(min_amount, max_amount)
    error_text_template = await get_bot_text(key=text_key, default=default, lang=lang)
    await event.respond(
        error_text_template.format(**placeholders),
        buttons=await keyboards.balance_amount_error_rows(),
    )


async def respond_deposit_numeric_error(
    event,
    *,
    text_key: str,
    default: str,
    lang: str = "fa",
) -> None:
    error_text = await get_bot_text(key=text_key, default=default, lang=lang)
    await event.respond(error_text, buttons=await keyboards.balance_amount_error_rows())


async def manual_card_amount_placeholders(
    amount_toman: int,
    settings,
    *,
    payable_amount: int | None = None,
    amount_offset: int | None = None,
) -> dict[str, str]:
    display = int(payable_amount) if payable_amount else int(amount_toman)
    amount_rial = display * 10
    formatted_toman = f"{display:,}"
    formatted_rial = f"{amount_rial:,}"
    placeholders = manual_card_limit_placeholders(settings)
    ttl_minutes = int(getattr(settings, "forapp_ttl_minutes", 30) or 30)
    forapp_on = bool(getattr(settings, "forapp_enabled", False)) and bool(payable_amount)
    if forapp_on:
        payable_note = (
            f"⚡ این مبلغ اختصاصی شماست و تا {ttl_minutes} دقیقه معتبر است.\n"
            "مبلغ را دقیقاً همین‌طور واریز کنید؛ پرداخت به صورت خودکار تایید "
            "و به کیف پول اضافه می‌شود و نیازی به ارسال رسید نیست."
        )
        receipt_hint = (
            "فقط در صورتی که بعد از واریز، تایید خودکار انجام نشد، از طریق دکمه زیر "
            "مراحل کارت‌به‌کارت (ارسال رسید) را ادامه دهید."
        )
    else:
        payable_note = ""
        receipt_hint = (
            "🏧 پس از انجام واریز، جهت ثبت و بررسی پرداخت، از طریق دکمه زیر "
            "مراحل کارت‌به‌کارت را ادامه دهید."
        )
    placeholders.update(
        {
            "amount": formatted_toman,
            "amount_toman": formatted_toman,
            "amount_rial": formatted_rial,
            "card_line": await build_manual_card_line(settings),
            "base_amount": f"{int(amount_toman):,}",
            "payable_amount": formatted_toman,
            "payable_rial": formatted_rial,
            "amount_offset": f"{int(amount_offset or 0):,}",
            "payable_note": payable_note,
            "receipt_hint": receipt_hint,
        }
    )
    return placeholders


# How far back we look for an already-credited transfer when a receipt
# arrives without a matching pending tx (protects cleared-state resends).
FORAPP_RECEIPT_GUARD_SECONDS = 24 * 60 * 60

FORAPP_ALREADY_APPROVED_TEXT = (
    "⚡ این پرداخت قبلاً به صورت خودکار تایید و مبلغ آن به کیف پول اضافه شده است.\n"
    "نیازی به ارسال رسید نیست."
)


async def get_forapp_pre_tx(user_id: int):
    """Pending ForApp tx reserved for this user's current top-up, if any."""
    try:
        pre_tx_id = await get_data(user_id, "forapp_tx_id")
    except Exception:
        return None
    if not pre_tx_id:
        return None
    try:
        return await TransactionCRUD().get(int(pre_tx_id))
    except Exception:
        return None


async def find_approved_forapp_transfer(user_id: int):
    """A recent auto-credited transfer with no receipt attached, if any.

    Returns None when ForApp is disabled — without auto-verify there is
    nothing that could have been credited behind the receipt flow's back.
    """
    settings = await SettingsManager().get_settings()
    if not settings or not bool(getattr(settings, "forapp_enabled", False)):
        return None
    import time as _time

    since = int(_time.time()) - FORAPP_RECEIPT_GUARD_SECONDS
    try:
        return await TransactionCRUD().find_recent_approved_payable_without_receipt(
            int(user_id), since
        )
    except Exception:
        return None


async def reserve_forapp_for_user(user_id: int, base_amount: int) -> tuple[int, int, object | None]:
    """Reserve a unique payable and pre-create the pending manual tx.

    Returns ``(payable, offset, tx)``. Falls back to ``(base, 0, None)`` when
    ForApp is disabled or reservation fails, so the legacy receipt flow keeps
    working untouched.
    """
    from app.db.crud.transactions import TransactionCRUD, reserve_unique_payable_for_manual
    from app.telegram.state import set_data as _set_data

    settings = await SettingsManager().get_settings()
    if not settings or not bool(getattr(settings, "forapp_enabled", False)):
        return int(base_amount), 0, None
    try:
        min_offset = int(getattr(settings, "forapp_offset_min", 1) or 1)
        max_offset = int(getattr(settings, "forapp_offset_max", 999) or 999)
        ttl_minutes = int(getattr(settings, "forapp_ttl_minutes", 30) or 30)
    except (TypeError, ValueError):
        min_offset, max_offset, ttl_minutes = 1, 999, 30
    try:
        payable, offset = await reserve_unique_payable_for_manual(
            int(base_amount),
            ttl_seconds=max(int(ttl_minutes) * 60, 60),
            min_offset=min_offset,
            max_offset=max_offset,
        )
    except Exception:
        return int(base_amount), 0, None
    try:
        tx = await TransactionCRUD().create(
            user_id=int(user_id),
            amount=int(base_amount),
            method="manual",
            payable_amount=int(payable),
            amount_offset=int(offset),
        )
    except Exception:
        return int(payable), int(offset), None
    try:
        # Two users can reserve the same payable concurrently (read-then-create
        # race). If a *different* pending tx already holds it, re-reserve.
        import time as _time

        from app.db.crud.transactions import reserve_unique_payable_for_manual as _rereserve

        _since = int(_time.time()) - max(int(ttl_minutes) * 60, 60)
        for _ in range(3):
            clash = await TransactionCRUD().find_pending_manual_by_payable(int(payable), since_ts=_since)
            if clash is None or int(clash.id) == int(tx.id):
                break
            payable, offset = await _rereserve(
                int(base_amount),
                ttl_seconds=max(int(ttl_minutes) * 60, 60),
                min_offset=min_offset,
                max_offset=max_offset,
            )
            tx = await TransactionCRUD().update(tx.id, payable_amount=int(payable), amount_offset=int(offset)) or tx
    except Exception:
        pass
    try:
        await _set_data(int(user_id), "forapp_payable", int(payable))
        await _set_data(int(user_id), "forapp_offset", int(offset))
        await _set_data(int(user_id), "forapp_tx_id", int(tx.id))
    except Exception:
        pass
    return int(payable), int(offset), tx


async def remember_balance_flow_message(user_id: int, message_id: int) -> None:
    await set_data(user_id, states.BALANCE_FLOW_MSG_STEP, message_id)


async def get_balance_flow_message_id(user_id: int, event) -> int | None:
    stored = await get_data(user_id, states.BALANCE_FLOW_MSG_STEP)
    if stored:
        return int(stored)
    if getattr(event, "message_id", None):
        return int(event.message_id)
    return None


async def clear_reply_keyboard(event) -> None:
    try:
        clear_msg = await event.respond("⏳", buttons=Button.clear())
        await clear_msg.delete()
    except Exception:
        pass


async def respond_after_clearing_keyboard(event, text: str, *, buttons=None, parse_mode=None):
    await clear_reply_keyboard(event)
    kwargs = {}
    if buttons is not None:
        kwargs["buttons"] = buttons
    if parse_mode is not None:
        kwargs["parse_mode"] = parse_mode
    return await event.respond(text, **kwargs)


async def manual_card_prompt_amount(event) -> None:
    settings = await SettingsManager().get_settings()
    placeholders = manual_card_limit_placeholders(settings)
    amount_request_text = await get_bot_text(
        key="manual_card_amount_request",
        default=texts.MANUAL_CARD_AMOUNT_REQUEST_DEFAULT,
        lang="fa",
    )
    text = amount_request_text.format(**placeholders)
    await event.edit(text, buttons=await balance_flow_cancel_rows())
    await remember_balance_flow_message(event.sender_id, event.message_id)


async def return_to_balance_menu(event) -> None:
    user_id = event.sender_id
    pending = await get_pending_for_user(user_id)
    # Resume direct-pay only when the user is already inside that payment flow.
    # Do not treat a leftover pending buy as direct-pay when opening balance from renew/upgrade.
    was_direct = await is_direct_pay_active(user_id)
    await clear_user(user_id)
    settings = await SettingsManager().get_settings()
    info = await UserCRUD().read_user(user_id)
    lang = info.language if info and info.language else "fa"

    if was_direct and pending and pending.get("status") in ACTIVE_STATUSES:
        topup = int(pending.get("topup_amount") or 0)
        required = int(pending.get("amount") or 0)
        payload = pending.get("payload") or {}
        product_label = str(payload.get("product_label") or "-")
        volume = str(payload.get("volume") or "-")
        await set_data(user_id, REDIS_DIRECT_PAY_ACTIVE, "1")
        await set_data(user_id, REDIS_MABLAGH, topup)
        if pending.get("kind") == KIND_RENEW:
            intro_template = await get_bot_text(
                key="direct_pay_renew_topup_intro",
                default=DIRECT_PAY_RENEW_TOPUP_INTRO_DEFAULT,
                lang=lang,
            )
        else:
            intro_template = await get_bot_text(
                key="direct_pay_topup_intro",
                default=DIRECT_PAY_TOPUP_INTRO_DEFAULT,
                lang=lang,
            )
        intro_text = fill_placeholders(
            intro_template,
            product_label=product_label,
            volume=volume,
            topup_amount=topup,
            required=required,
            shortfall=topup,
        )
    else:
        if pending and pending.get("status") in ACTIVE_STATUSES:
            await cancel_pending_for_user(user_id)
        intro_text = await get_bot_text(
            key="add_balance_intro",
            default=texts.ADD_BALANCE_INTRO_DEFAULT,
            lang=lang,
        )

    intro_buttons = await create_inline_cartbcard(settings=settings, user=info)
    try:
        await event.edit(intro_text, buttons=intro_buttons)
        await remember_balance_flow_message(user_id, event.message_id)
    except Exception:
        await event.respond(intro_text, buttons=intro_buttons)
    await set_step(user_id=user_id, step=states.STEP_CART_B_CART)


async def return_to_home_menu(event) -> None:
    user_id = event.sender_id
    if await is_direct_pay_active(user_id) or await get_pending_for_user(user_id):
        await cancel_pending_for_user(user_id)
    await clear_user(user_id)
    info = await UserCRUD().read_user(user_id)
    lang = info.language if info and info.language else "fa"
    with contextlib.suppress(Exception):
        await event.delete()
    await event.respond(
        texts.RETURN_HOME_TEXT,
        buttons=await bhome_buttons(user_id, lang),
    )
    await set_step(user_id=user_id, step=states.STEP_HOME)


async def manual_card_send_channel_info(
    event, amount_toman: int, *, edit: bool = False, payable_amount: int | None = None
) -> None:
    settings = await SettingsManager().get_settings()
    if payable_amount is None:
        try:
            stored = await get_data(event.sender_id, "forapp_payable")
            payable_amount = int(stored) if stored else None
        except Exception:
            payable_amount = None
    placeholders = await manual_card_amount_placeholders(amount_toman, settings, payable_amount=payable_amount)
    text_template = await get_bot_text(
        key="manual_card_info",
        default=texts.MANUAL_CARD_INFO_DEFAULT,
        lang="fa",
    )
    text = text_template.format(**placeholders)
    buttons = await keyboards.manual_card_channel_info_rows()
    flow_msg_id = await get_balance_flow_message_id(event.sender_id, event)
    event_msg_id = getattr(event, "message_id", None)
    same_message = bool(flow_msg_id and event_msg_id and int(flow_msg_id) == int(event_msg_id))

    # Callback path: edit the payment menu in place. Never delete that same message
    # (legacy flow deletes the user's amount NewMessage, which is a different id).
    if edit and (not flow_msg_id or same_message):
        await event.edit(text, buttons=buttons)
        await remember_balance_flow_message(event.sender_id, event.message_id)
        return

    if flow_msg_id:
        await event.client.edit_message(event.chat_id, flow_msg_id, text, buttons=buttons)
        await remember_balance_flow_message(event.sender_id, flow_msg_id)
        if event_msg_id and int(event_msg_id) != int(flow_msg_id):
            with contextlib.suppress(Exception):
                await event.delete()
        return

    sent = await event.respond(text, buttons=buttons)
    await remember_balance_flow_message(event.sender_id, sent.id)


def to_rial(amount: int) -> int:
    rial_amount = amount * 10
    rial_str = str(rial_amount)

    if len(rial_str) <= 3:
        modified_digits = [str(random.randint(0, 9)) for _ in range(len(rial_str))]
    else:
        modified_digits = list(rial_str[:-3]) + [str(random.randint(0, 9)) for _ in range(3)]

    modified_rial_str = "".join(modified_digits)
    return int(modified_rial_str)


async def _require_balance_payment_step(event) -> bool:
    if await get_step(event.sender_id) == states.STEP_CART_B_CART:
        return True
    await notify_session_expired(event)
    return False


async def _request_phone_for_balance_payment(event) -> None:
    await event.delete()
    await event.respond(texts.PHONE_VERIFY_PROMPT, buttons=keyboards.phone_verify_button())
    await set_step(user_id=event.sender_id, step=states.STEP_CONF_NUMBER)


async def _prompt_crypto_amount(event, *, step: str, currency_text: str) -> None:
    settings = await SettingsManager().get_settings()
    if not settings.arz_mode:
        await event.answer(texts.PAYMENT_DISABLED_ALERT, alert=True)
        return
    await event.edit(
        texts.CRYPTO_AMOUNT_PROMPT_TEMPLATE.format(
            min=f"{settings.crypto_deposit_min:,}",
            max=f"{settings.crypto_deposit_max:,}",
            currency=currency_text,
        ),
        buttons=await balance_flow_cancel_rows(),
    )
    await remember_balance_flow_message(event.sender_id, event.message_id)
    await set_step(user_id=event.sender_id, step=step)


def _is_nav_command(msg: str) -> bool:
    msg_lower = msg.lower().strip()
    return (
        msg_lower.startswith(states.NAV_COMMAND_PREFIXES[0])
        or msg_lower.startswith(states.NAV_COMMAND_PREFIXES[1])
        or msg_lower in states.LEGACY_CANCEL_MESSAGES
    )


async def _build_user_info_log(user_id: int, reduser) -> str:
    try:
        telegram_user = await Kenzo.get_entity(user_id)
        user_first_name = telegram_user.first_name or None
        user_last_name = telegram_user.last_name or None
        user_username = telegram_user.username or None
    except Exception:
        user_first_name = None
        user_last_name = None
        user_username = None

    user_info_parts = [f"👤 **شناسه کاربر:** `{reduser.id}` | [پروفایل کاربر](tg://user?id={reduser.id})"]
    if user_first_name or user_last_name:
        full_name = " ".join(filter(None, [user_first_name, user_last_name]))
        user_info_parts.append(f"✏️ **نام:** {full_name}")
    if user_username:
        user_info_parts.append(f"📱 **یوزرنیم:** @{user_username}")
    return "\n".join(user_info_parts)


async def menu_add_balance_filter(event):
    if event.is_channel or not event.is_private:
        return False
    if is_keyboard_config_step(await get_step(event.sender_id)):
        return False

    msg = event.message.text or event.message.message
    if not msg:
        return False

    param = extract_start_param(event)
    return bool(
        msg == await get_button_text("bt.menu_add_balance", states.MENU_ADD_BALANCE_TEXT)
        or msg == states.MENU_ADD_BALANCE_TEXT
        or msg == states.CHARGE_COMMAND
        or (param and param.lower() == "charge")
    )


@bot_is_offline
async def menu_add_balance_handler(event: Message):
    if not await ensure_channel_membership(event):
        raise events.StopPropagation

    msg = event.message.text or event.message.message
    user_id = event.sender_id
    info = await UserCRUD().read_user(user_id)
    lang = info.language if info and info.language else "fa"

    param = extract_start_param(event)
    if (
        msg == (await get_button_text("bt.menu_add_balance", states.MENU_ADD_BALANCE_TEXT))
        or msg == states.MENU_ADD_BALANCE_TEXT
        or msg == states.CHARGE_COMMAND
        or (param and param.lower() == "charge")
    ):
        settings = await SettingsManager().get_settings()

        intro_text = await get_bot_text(
            key="add_balance_intro",
            default=texts.ADD_BALANCE_INTRO_DEFAULT,
            lang=lang,
        )
        sent = await respond_after_clearing_keyboard(
            event,
            intro_text,
            buttons=await create_inline_cartbcard(settings=settings, user=info),
        )
        await remember_balance_flow_message(user_id, sent.id)
        await set_step(user_id=user_id, step=states.STEP_CART_B_CART)
        raise events.StopPropagation


async def manual_card_step_filter(event):
    if event.is_channel or not event.is_private:
        return False
    if (await get_step(event.sender_id)) != states.STEP_CART_B_CART_AMOUNT:
        return False
    msg = event.message.message
    if not msg:
        return False
    return not _is_nav_command(msg)


@bot_is_offline
async def cart_b_cart_amount_handler(event: Message):
    msg = event.message.message

    if msg.isdigit():
        amount = int(msg)
        settings = await SettingsManager().get_settings()
        if amount < settings.manual_deposit_min or amount > settings.manual_deposit_max:
            await respond_deposit_amount_range_error(
                event,
                text_key="manual_card_amount_range_error",
                default=texts.MANUAL_CARD_AMOUNT_RANGE_ERROR_DEFAULT,
                min_amount=settings.manual_deposit_min,
                max_amount=settings.manual_deposit_max,
            )
            raise events.StopPropagation
        await set_data(event.sender_id, "mablagh", amount)
        payable, _offset, _tx = await reserve_forapp_for_user(event.sender_id, amount)
        await manual_card_send_channel_info(event, amount, edit=False, payable_amount=payable)
        await set_step(event.sender_id, step=states.STEP_CART_B_CART2)
        raise events.StopPropagation
    await respond_deposit_numeric_error(
        event,
        text_key="manual_card_numeric_error",
        default=texts.MANUAL_CARD_NUMERIC_ERROR_DEFAULT,
    )
    raise events.StopPropagation


async def balance_cancel_legacy_text_filter(event):
    if event.is_channel or not event.is_private:
        return False
    if await get_step(event.sender_id) not in states.BALANCE_FLOW_CANCEL_STEPS:
        return False
    msg = (event.message.message or "").strip()
    return msg in states.LEGACY_CANCEL_MESSAGES


@bot_is_offline
async def balance_cancel_legacy_text_handler(event: Message):
    await return_to_balance_menu(event)
    raise events.StopPropagation


async def receipt_photo_filter(event):
    if event.is_channel or not event.is_private:
        return False
    if (await get_step(event.sender_id)) != states.STEP_MABLAGH_SHARJ:
        return False
    msg = event.message.message
    return not (msg and _is_nav_command(msg))


@bot_is_offline
async def mablagh_sharj_handler(event: Message):
    if event.message.photo:
        photo = event.message.photo
        mablagh = await get_data(event.sender_id, "mablagh")

        manual_card_log_destination = await LogChannelManager().get_log_channel_destination(LogType.MANUAL_CARD.value)
        if not manual_card_log_destination and LOG_CHANNEL is None:
            log_channel_missing_template = await get_bot_text(
                key="manual_card_log_channel_missing",
                default=texts.MANUAL_CARD_LOG_CHANNEL_MISSING_DEFAULT,
                lang="fa",
            )
            await event.respond(log_channel_missing_template, buttons=await bhome_buttons(event.sender_id, "fa"))
            await set_step(event.sender_id, step=states.STEP_START)
            await clear_user(event.sender_id)
            raise events.StopPropagation

        phash_str: str | None = None

        photo_bytes = await event.client.download_media(photo, bytes)
        if photo_bytes:
            phash_str = compute_receipt_phash(photo_bytes)
            if phash_str:
                receipt_hash_crud = ReceiptHashCRUD()
                receipt_row = await receipt_hash_crud.try_insert(phash_str, int(event.sender_id))
                if receipt_row is None:
                    receipt_confirmed_template = await get_bot_text(
                        key="manual_card_receipt_confirmed",
                        default=texts.MANUAL_CARD_RECEIPT_CONFIRMED_DEFAULT,
                        lang="fa",
                    )
                    await event.respond(
                        receipt_confirmed_template.format(amount=f"{int(mablagh):,}"),
                        buttons=await bhome_buttons(event.sender_id, "fa"),
                    )
                    await set_step(event.sender_id, step=states.STEP_START)
                    await clear_user(event.sender_id)

                    reduser = await UserCRUD().read_user(user_id=int(event.sender_id))
                    crud = TransactionCRUD()
                    manual_approved = await crud.count_user_transactions(
                        event.sender_id, status="approved", method="manual"
                    )
                    manual_rejected = await crud.count_user_transactions(
                        event.sender_id, status="rejected", method="manual"
                    )
                    auto_approved = await crud.count_user_transactions(
                        event.sender_id, status="approved", method="auto"
                    )
                    auto_rejected = await crud.count_user_transactions(
                        event.sender_id, status="rejected", method="auto"
                    )
                    user_info = await _build_user_info_log(event.sender_id, reduser)

                    log_message_dup = (
                        f"{texts.DUPLICATE_RECEIPT_LOG_HEADER}"
                        f"{user_info}\n"
                        f"🔢 **شماره تلفن:** {reduser.number}\n"
                        f"💰 **موجودی:** `{reduser.amount:,}` تومان\n"
                        f"🛡️ **مبلغ وارد شده** `{int(mablagh):,}` تومان\n"
                        f"📊 **دستی:** تایید `{manual_approved:,}` | رد `{manual_rejected:,}`\n"
                        f"🤖 **خودکار:** تایید `{auto_approved:,}` | رد `{auto_rejected:,}`\n"
                        f"❌ **وضعیت:** رسید تکراری (hash قبلاً ثبت شده)"
                    )

                    await send_log_message(
                        log_type=LogType.MANUAL_CARD,
                        file=photo,
                        caption=log_message_dup,
                        force_document=False,
                    )
                    raise events.StopPropagation

        receipt_confirmed_template = await get_bot_text(
            key="manual_card_receipt_confirmed",
            default=texts.MANUAL_CARD_RECEIPT_CONFIRMED_DEFAULT,
            lang="fa",
        )
        mesg_resid = receipt_confirmed_template.format(amount=f"{int(mablagh):,}")
        await event.respond(mesg_resid, buttons=await bhome_buttons(event.sender_id, "fa"))
        reduser = await UserCRUD().read_user(user_id=int(event.sender_id))
        # Reuse the ForApp pre-created pending tx (holds the unique payable amount)
        # so the SMS webhook and the photo receipt point at the same record.
        # A receipt arriving after the transfer was already auto-credited is
        # refused — accepting it would mint a second tx for the same money.
        tx = await get_forapp_pre_tx(event.sender_id)
        if tx is not None and int(tx.user_id) != int(event.sender_id):
            tx = None
        if tx is not None and tx.status != "pending":
            await event.respond(
                FORAPP_ALREADY_APPROVED_TEXT,
                buttons=await bhome_buttons(event.sender_id, "fa"),
            )
            await set_step(event.sender_id, step=states.STEP_START)
            await clear_user(event.sender_id)
            raise events.StopPropagation
        if tx is None:
            approved = await find_approved_forapp_transfer(event.sender_id)
            if approved is not None:
                payable = int(approved.payable_amount or approved.amount)
                await event.respond(
                    FORAPP_ALREADY_APPROVED_TEXT + f"\n\n💵 مبلغ: `{payable:,}` تومان",
                    buttons=await bhome_buttons(event.sender_id, "fa"),
                )
                await set_step(event.sender_id, step=states.STEP_START)
                await clear_user(event.sender_id)
                raise events.StopPropagation
            try:
                pre_payable = await get_data(event.sender_id, "forapp_payable")
                pre_offset = await get_data(event.sender_id, "forapp_offset")
            except Exception:
                pre_payable = pre_offset = None
            tx = await TransactionCRUD().create(
                user_id=int(event.sender_id),
                amount=int(mablagh),
                method="manual",
                payable_amount=int(pre_payable) if pre_payable else None,
                amount_offset=int(pre_offset) if pre_offset else None,
            )
        if await is_direct_pay_active(event.sender_id) or await get_pending_for_user(event.sender_id):
            await link_transaction(int(event.sender_id), int(tx.id))
        rule_crud = ManualAutoApproveRuleCRUD()
        matched_rule = await rule_crud.schedule_for_transaction(tx)
        tx = await TransactionCRUD().get(tx.id) or tx
        successful_count = await TransactionCRUD().count_user_transactions(
            tx.user_id, status="approved", method="manual"
        )
        crud = TransactionCRUD()
        manual_approved = await crud.count_user_transactions(tx.user_id, status="approved", method="manual")
        manual_rejected = await crud.count_user_transactions(tx.user_id, status="rejected", method="manual")
        auto_approved = await crud.count_user_transactions(tx.user_id, status="approved", method="auto")
        auto_rejected = await crud.count_user_transactions(tx.user_id, status="rejected", method="auto")

        user_info = await _build_user_info_log(event.sender_id, reduser)

        auto_status = rule_crud.format_status_line(
            matched_rule,
            auto_approve_at=getattr(tx, "auto_approve_at", None),
            successful_count=successful_count,
        )
        log_message = (
            f"{texts.MANUAL_RECEIPT_LOG_HEADER}"
            f"{user_info}\n"
            f"🔢 **شماره تلفن:** {reduser.number}\n"
            f"💰 **موجودی:** `{reduser.amount:,}` تومان\n"
            f"🛡️ **مبلغ وارد شده** `{int(mablagh):,}` تومان\n"
            f"{auto_status}\n"
            f"📊 **دستی:** تایید `{manual_approved:,}` | رد `{manual_rejected:,}`\n"
            f"🤖 **خودکار:** تایید `{auto_approved:,}` | رد `{auto_rejected:,}`\n"
        )

        message = await send_log_message(
            log_type=LogType.MANUAL_CARD,
            file=photo,
            caption=log_message,
            buttons=keyboards.transaction_review_buttons(tx.id),
        )

        if message and hasattr(message, "id"):
            await TransactionCRUD().update(
                tx.id,
                message_id=message.id,
                message_chat_id=message.chat_id,
            )
        if phash_str:
            await ReceiptHashCRUD().update_transaction_id(phash_str, tx.id)
        await set_step(event.sender_id, step=states.STEP_START)
        await clear_user(event.sender_id)
        raise events.StopPropagation

    error_text = await get_bot_text(
        key="manual_card_receipt_photo_error",
        default=texts.MANUAL_CARD_RECEIPT_PHOTO_ERROR_DEFAULT,
        lang="fa",
    )
    await event.respond(error_text)
    raise events.StopPropagation


async def create_crypto_invoice(event, *, arz: str, amount_irt: int) -> None:
    """Create crypto deposit invoice for TRX/USDT/TON and link direct-pay if active."""
    lang = "fa"
    settings = await SettingsManager().get_settings()
    amount = int(amount_irt)
    if amount < settings.crypto_deposit_min or amount > settings.crypto_deposit_max:
        await respond_deposit_amount_range_error(
            event,
            text_key="crypto_amount_range_error",
            default=texts.CRYPTO_AMOUNT_RANGE_ERROR_DEFAULT,
            min_amount=settings.crypto_deposit_min,
            max_amount=settings.crypto_deposit_max,
        )
        return
    if await count_pending_orders(event.sender_id) >= 3:
        await event.respond(
            texts.PENDING_ORDERS_LIMIT,
            buttons=await bhome_buttons(event.sender_id, lang),
        )
        await set_step(event.sender_id, states.STEP_HOME)
        return

    order = await allocate_order_id()
    if order is None:
        await event.respond(texts.CRYPTO_INVOICE_CREATE_FAILED, buttons=await bhome_buttons(event.sender_id, lang))
        await set_step(event.sender_id, states.STEP_HOME)
        return
    arz_lower = arz.lower()
    reserved = {str(p.amount) for p in await CryptoPaymentsCRUD().get_pending_by_arz(arz_lower)}
    open_wallet_url: str | None = None
    if arz_lower == "trx":
        crypto_amount = await calculate_trx_amount_with_tax(int(settings.arz_trx), amount, reserved_amounts=reserved)
        wallet = await WalletCRUD().get_wallet_by_type("TRX")
        if not wallet:
            await event.respond(texts.WALLET_NOT_FOUND_TRX)
            await set_step(event.sender_id, states.STEP_HOME)
            return
        wallet_key = wallet.address
        uri = f"tron:{wallet_key}?amount={crypto_amount}"
        logo_path = "app/assets/tron.png"
        file_name = f"Tron_{order}.png"
        message_text = (
            f"<b>✅ فاکتور پرداخت ارزی TRX ایجاد شد.</b>\n"
            f"- -\n"
            f"➿ شماره فاکتور : <code>{order}</code>\n"
            f"🕰 مهلت پرداخت : 30 دقیقه\n"
            f"<b>💵 مبلغ فاکتور :</b> <code>{amount:,}</code> <b>هزارتومان</b>\n"
            f"<b>📊 قیمت دلار:</b> <code>{settings.arz_usd:,}</code> <b>هزارتومان</b>\n"
            f"<b>📊 قیمت ترون:</b> <code>{settings.arz_trx:,}</code> <b>هزارتومان</b>\n"
            f"<b>🧬 شبکه:</b> <code>trc20</code>\n"
            f"<b>💰 مبلغ </b> <code>{crypto_amount}</code> <b> ترون به ادرس کیف پول زیر واریز کنید </b>\n\n"
            f"<code>{wallet_key}</code>\n\n"
            f"🪩 همچنین میتونید کیو ار کد بالا رو اسکن کنید"
        )
        log_text = (
            "#فاکتور_جدید_ترون\n"
            f"👤 شناسه کاربر: <code>{event.sender_id}</code> | "
            f"<a href='tg://user?id={event.sender_id}'>پروفایل کاربر</a>\n"
            f"💡 شماره فاکتور: <code>{order}</code>\n"
            f"💵 مبلغ فاکتور: <code>{amount:,}</code> تومان\n"
            f"💰 مقدار ترون: <code>{crypto_amount}</code>\n"
            f"📊 قیمت دلار: <code>{settings.arz_usd:,}</code> هزار تومان\n"
            f"📊 قیمت ترون: <code>{settings.arz_trx:,}</code> هزار تومان"
        )
    elif arz_lower == "usdt":
        crypto_amount = await calculate_usdt_amount_with_tax(int(settings.arz_usd), amount, reserved_amounts=reserved)
        wallet = await WalletCRUD().get_wallet_by_type("USDT")
        if not wallet:
            await event.respond(texts.WALLET_NOT_FOUND_USDT)
            await set_step(event.sender_id, states.STEP_HOME)
            return
        wallet_key = wallet.address
        uri = f"tron:{wallet_key}?amount={crypto_amount}&token=TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
        logo_path = "app/assets/tron.png"
        file_name = f"USDT_{order}.png"
        message_text = (
            f"<b>✅ فاکتور پرداخت ارزی USDT ایجاد شد.</b>\n"
            f"- -\n"
            f"➿ شماره فاکتور : <code>{order}</code>\n"
            f"🕰 مهلت پرداخت : 30 دقیقه\n"
            f"<b>💵 مبلغ فاکتور :</b> <code>{amount:,}</code> <b>هزارتومان</b>\n"
            f"<b>📊 قیمت دلار:</b> <code>{settings.arz_usd:,}</code> <b>هزارتومان</b>\n"
            f"<b>🧬 شبکه:</b> <code>trc20</code>\n"
            f"<b>💰 مبلغ </b> <code>{crypto_amount}</code> <b> USDT به ادرس کیف پول زیر واریز کنید </b>\n\n"
            f"<code>{wallet_key}</code>\n\n"
            f"🪩 همچنین میتونید کیو ار کد بالا رو اسکن کنید"
        )
        log_text = (
            "#فاکتور_جدید_USDT\n"
            f"👤 شناسه کاربر: <code>{event.sender_id}</code> | "
            f"<a href='tg://user?id={event.sender_id}'>پروفایل کاربر</a>\n"
            f"💡 شماره فاکتور: <code>{order}</code>\n"
            f"💵 مبلغ فاکتور: <code>{amount:,}</code> تومان\n"
            f"💰 مقدار USDT: <code>{crypto_amount}</code>\n"
            f"📊 قیمت دلار: <code>{settings.arz_usd:,}</code> هزار تومان"
        )
    elif arz_lower == "usdt-ton":
        crypto_amount = await calculate_usdt_amount_with_tax(int(settings.arz_usd), amount, reserved_amounts=reserved)
        wallet = await WalletCRUD().get_wallet_by_type(USDT_TON)
        if not wallet:
            await event.respond(texts.WALLET_NOT_FOUND_USDT_TON)
            await set_step(event.sender_id, states.STEP_HOME)
            return
        wallet_key = wallet.address
        usdt_units = round(float(crypto_amount) * 1_000_000)
        uri = f"ton://transfer/{wallet_key}?jetton={USDT_TON_JETTON}&amount={usdt_units}"
        open_wallet_url = keyboards.tonkeeper_usdt_transfer_url(wallet_key, crypto_amount, USDT_TON_JETTON)
        logo_path = "app/assets/ton.png"
        file_name = f"USDT_TON_{order}.png"
        message_text = (
            f"<b>✅ فاکتور پرداخت ارزی USDT-TON ایجاد شد.</b>\n"
            f"- -\n"
            f"➿ شماره فاکتور : <code>{order}</code>\n"
            f"🕰 مهلت پرداخت : 30 دقیقه\n"
            f"<b>💵 مبلغ فاکتور :</b> <code>{amount:,}</code> <b>تومان</b>\n"
            f"<b>📊 قیمت دلار:</b> <code>{settings.arz_usd:,}</code> <b>هزارتومان</b>\n"
            f"<b>🧬 شبکه:</b> <code>{USDT_TON}</code>\n"
            f"<b>💰 مبلغ </b> <code>{crypto_amount}</code> <b> USDT به آدرس کیف پول زیر واریز کنید </b>\n\n"
            f"<code>{wallet_key}</code>\n\n"
            f"🪩 همچنین میتونید کیو ار کد بالا رو اسکن کنید"
        )
        log_text = (
            "#فاکتور_جدید_USDT_TON\n"
            f"👤 شناسه کاربر: <code>{event.sender_id}</code> | "
            f"<a href='tg://user?id={event.sender_id}'>پروفایل کاربر</a>\n"
            f"💡 شماره فاکتور: <code>{order}</code>\n"
            f"💵 مبلغ فاکتور: <code>{amount:,}</code> تومان\n"
            f"💰 مقدار USDT: <code>{crypto_amount}</code>\n"
            f"🧬 شبکه: {USDT_TON}\n"
            f"📊 قیمت دلار: <code>{settings.arz_usd:,}</code> هزار تومان"
        )
    elif arz_lower == "usdt-bep20":
        crypto_amount = await calculate_usdt_amount_with_tax(int(settings.arz_usd), amount, reserved_amounts=reserved)
        wallet = await WalletCRUD().get_wallet_by_type(USDT_BEP20)
        if not wallet:
            await event.respond(texts.WALLET_NOT_FOUND_USDT_BEP20)
            await set_step(event.sender_id, states.STEP_HOME)
            return
        wallet_key = wallet.address
        usdt_units = int(Decimal(str(crypto_amount)) * (Decimal(10) ** 18))
        uri = f"ethereum:{USDT_BEP20_CONTRACT}@56/transfer?address={wallet_key}&uint256={usdt_units}"
        logo_path = "app/assets/bsc.png"
        file_name = f"USDT_BEP20_{order}.png"
        message_text = (
            f"<b>✅ فاکتور پرداخت ارزی USDT-BEP20 ایجاد شد.</b>\n"
            f"- -\n"
            f"➿ شماره فاکتور : <code>{order}</code>\n"
            f"🕰 مهلت پرداخت : 30 دقیقه\n"
            f"<b>💵 مبلغ فاکتور :</b> <code>{amount:,}</code> <b>تومان</b>\n"
            f"<b>📊 قیمت دلار:</b> <code>{settings.arz_usd:,}</code> <b>هزارتومان</b>\n"
            f"<b>🧬 شبکه:</b> <code>{USDT_BEP20}</code>\n"
            f"<b>💰 مبلغ </b> <code>{crypto_amount}</code> <b> USDT به آدرس کیف پول زیر واریز کنید </b>\n\n"
            f"<code>{wallet_key}</code>\n\n"
            f"🪩 همچنین میتونید کیو ار کد بالا رو اسکن کنید"
        )
        log_text = (
            "#فاکتور_جدید_USDT_BEP20\n"
            f"👤 شناسه کاربر: <code>{event.sender_id}</code> | "
            f"<a href='tg://user?id={event.sender_id}'>پروفایل کاربر</a>\n"
            f"💡 شماره فاکتور: <code>{amount:,}</code> تومان\n"
            f"💰 مقدار USDT: <code>{crypto_amount}</code>\n"
            f"🧬 شبکه: {USDT_BEP20}\n"
            f"📊 قیمت دلار: <code>{settings.arz_usd:,}</code> هزار تومان"
        )
    elif arz_lower == "ton":
        crypto_amount = await calculate_ton_amount_with_tax(int(settings.arz_ton), amount, reserved_amounts=reserved)
        wallet = await WalletCRUD().get_wallet_by_type("TON")
        if not wallet:
            await event.respond(texts.WALLET_NOT_FOUND_TON)
            await set_step(event.sender_id, states.STEP_HOME)
            return
        wallet_key = wallet.address
        nano_amount = int(float(crypto_amount) * 1e9)
        uri = f"ton://transfer/{wallet_key}?amount={nano_amount}"
        open_wallet_url = keyboards.tonkeeper_transfer_url(wallet_key, crypto_amount)
        logo_path = "app/assets/ton.png"
        file_name = f"TON_{order}.png"
        message_text = (
            f"<b>✅ فاکتور پرداخت ارزی TON ایجاد شد.</b>\n"
            f"- -\n"
            f"➿ شماره فاکتور : <code>{order}</code>\n"
            f"🕰 مهلت پرداخت : 30 دقیقه\n"
            f"<b>💵 مبلغ فاکتور :</b> <code>{amount:,}</code> <b>تومان</b>\n"
            f"<b>📊 قیمت TON:</b> <code>{settings.arz_ton:,}</code> <b>هزارتومان</b>\n"
            f"<b>📊 قیمت دلار:</b> <code>{settings.arz_usd:,}</code> <b>هزارتومان</b>\n"
            f"<b>💰 مبلغ </b> <code>{crypto_amount}</code> <b> TON به آدرس کیف پول زیر واریز کنید </b>\n\n"
            f"<code>{wallet_key}</code>\n\n"
            f"🪩 همچنین میتونید کیو ار کد بالا رو اسکن کنید"
        )
        log_text = (
            "#فاکتور_جدید_TON\n"
            f"👤 شناسه کاربر: <code>{event.sender_id}</code> | "
            f"<a href='tg://user?id={event.sender_id}'>پروفایل کاربر</a>\n"
            f"💡 شماره فاکتور: <code>{order}</code>\n"
            f"💵 مبلغ فاکتور: <code>{amount:,}</code> تومان\n"
            f"💰 مقدار TON: <code>{crypto_amount}</code>\n"
            f"📊 قیمت TON: <code>{settings.arz_ton:,}</code> هزار تومان\n"
            f"📊 قیمت دلار: <code>{settings.arz_usd:,}</code> هزار تومان"
        )
    elif arz_lower == "pol":
        crypto_amount = await calculate_pol_amount_with_tax(int(settings.arz_pol), amount, reserved_amounts=reserved)
        wallet = await WalletCRUD().get_wallet_by_type("POL")
        if not wallet:
            await event.respond(texts.WALLET_NOT_FOUND_POL)
            await set_step(event.sender_id, states.STEP_HOME)
            return
        wallet_key = wallet.address
        pol_wei = int(Decimal(str(crypto_amount)) * (Decimal(10) ** 18))
        uri = f"ethereum:{wallet_key}@137?value={pol_wei}"
        logo_path = "app/assets/pol.png"
        file_name = f"POL_{order}.png"
        message_text = (
            f"<b>✅ فاکتور پرداخت ارزی POL ایجاد شد.</b>\n"
            f"- -\n"
            f"➿ شماره فاکتور : <code>{order}</code>\n"
            f"🕰 مهلت پرداخت : 30 دقیقه\n"
            f"<b>💵 مبلغ فاکتور :</b> <code>{amount:,}</code> <b>تومان</b>\n"
            f"<b>📊 قیمت POL:</b> <code>{settings.arz_pol:,}</code> <b>هزارتومان</b>\n"
            f"<b>📊 قیمت دلار:</b> <code>{settings.arz_usd:,}</code> <b>هزارتومان</b>\n"
            f"<b>🧬 شبکه:</b> <code>Polygon</code>\n"
            f"<b>💰 مبلغ </b> <code>{crypto_amount}</code> <b> POL به آدرس کیف پول زیر واریز کنید </b>\n\n"
            f"<code>{wallet_key}</code>\n\n"
            f"🪩 همچنین میتونید کیو ار کد بالا رو اسکن کنید"
        )
        log_text = (
            "#فاکتور_جدید_POL\n"
            f"👤 شناسه کاربر: <code>{event.sender_id}</code> | "
            f"<a href='tg://user?id={event.sender_id}'>پروفایل کاربر</a>\n"
            f"💡 شماره فاکتور: <code>{order}</code>\n"
            f"💵 مبلغ فاکتور: <code>{amount:,}</code> تومان\n"
            f"💰 مقدار POL: <code>{crypto_amount}</code>\n"
            f"📊 قیمت POL: <code>{settings.arz_pol:,}</code> هزار تومان\n"
            f"📊 قیمت دلار: <code>{settings.arz_usd:,}</code> هزار تومان"
        )
    else:
        return

    qr = qrcode.QRCode(version=5, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=4)
    qr.add_data(uri)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    if await asyncio.to_thread(os.path.exists, logo_path):
        logo = Image.open(logo_path)
        qr_width, qr_height = qr_img.size
        logo_size = int(qr_width / 4)
        logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
        logo_position = ((qr_width - logo_size) // 2, (qr_height - logo_size) // 2)
        qr_img.paste(logo, logo_position, mask=logo)
    qr_file = BytesIO()
    qr_img.save(qr_file, format="PNG")
    qr_file.seek(0)
    qr_file.name = file_name
    logger.info("QR Code created in memory")

    # CallbackQuery uses edit/respond differently than Message
    respond = getattr(event, "respond", None)
    if respond is None:
        return

    saved = await add_order_crypto_payment(
        order_id=order,
        user_id=event.sender_id,
        arz=arz_lower,
        amount=crypto_amount,
        amount_irt=amount,
        createtime=Time_Date()["stamp"],
    )
    if not saved.get("success"):
        await event.respond(texts.CRYPTO_INVOICE_CREATE_FAILED, buttons=await bhome_buttons(event.sender_id, lang))
        await set_step(event.sender_id, states.STEP_HOME)
        return

    await event.respond("⏳", buttons=await bhome_buttons(event.sender_id, "fa"))
    invoice = await event.respond(
        message_text,
        file=qr_file,
        buttons=keyboards.crypto_copy_markup(crypto_amount, wallet_key, open_url=open_wallet_url),
        parse_mode="html",
    )
    await set_order_msg_id(order, invoice.id)
    if await is_direct_pay_active(event.sender_id) or await get_pending_for_user(event.sender_id):
        await link_crypto_order(int(event.sender_id), int(order))
        await clear_user(event.sender_id)

    await send_log_message(LogType.CRYPTO, message=log_text, parse_mode="html")
    await set_step(event.sender_id, states.STEP_HOME)


async def crypto_payment_trx_step_filter(event):
    if event.is_channel or not event.is_private:
        return False
    if (await get_step(event.sender_id)) != states.STEP_CRYPTO_TRX_2:
        return False
    msg = event.message.message
    if not msg:
        return False
    return not _is_nav_command(msg)


@bot_is_offline
async def crypto_payments_trx_handler(event: Message):
    msg = event.message.message
    if msg.isdigit():
        await create_crypto_invoice(event, arz="trx", amount_irt=int(msg))
        raise events.StopPropagation
    await respond_deposit_numeric_error(
        event,
        text_key="crypto_numeric_error",
        default=texts.CRYPTO_NUMERIC_ERROR_DEFAULT,
    )
    raise events.StopPropagation


async def crypto_payment_usdt_step_filter(event):
    if event.is_channel or not event.is_private:
        return False
    if (await get_step(event.sender_id)) != states.STEP_CRYPTO_USDT_2:
        return False
    msg = event.message.message
    if not msg:
        return False
    return not _is_nav_command(msg)


@bot_is_offline
async def crypto_payments_usdt_handler(event: Message):
    msg = event.message.message
    if msg.isdigit():
        await create_crypto_invoice(event, arz="usdt", amount_irt=int(msg))
        raise events.StopPropagation
    await respond_deposit_numeric_error(
        event,
        text_key="crypto_numeric_error",
        default=texts.CRYPTO_NUMERIC_ERROR_DEFAULT,
    )
    raise events.StopPropagation


async def crypto_payment_ton_step_filter(event):
    if event.is_channel or not event.is_private:
        return False
    if (await get_step(event.sender_id)) != states.STEP_CRYPTO_TON_2:
        return False
    msg = event.message.message
    if not msg:
        return False
    return not _is_nav_command(msg)


@bot_is_offline
async def crypto_payments_ton_handler(event: Message):
    msg = event.message.message
    if msg.isdigit():
        await create_crypto_invoice(event, arz="ton", amount_irt=int(msg))
        raise events.StopPropagation
    await respond_deposit_numeric_error(
        event,
        text_key="crypto_numeric_error",
        default=texts.CRYPTO_NUMERIC_ERROR_DEFAULT,
    )
    raise events.StopPropagation


async def crypto_payment_usdt_ton_step_filter(event):
    if event.is_channel or not event.is_private:
        return False
    if (await get_step(event.sender_id)) != states.STEP_CRYPTO_USDT_TON_2:
        return False
    msg = event.message.message
    if not msg:
        return False
    return not _is_nav_command(msg)


@bot_is_offline
async def crypto_payments_usdt_ton_handler(event: Message):
    msg = event.message.message
    if msg.isdigit():
        await create_crypto_invoice(event, arz="usdt-ton", amount_irt=int(msg))
        raise events.StopPropagation
    await respond_deposit_numeric_error(
        event,
        text_key="crypto_numeric_error",
        default=texts.CRYPTO_NUMERIC_ERROR_DEFAULT,
    )
    raise events.StopPropagation


async def crypto_payment_usdt_bep20_step_filter(event):
    if event.is_channel or not event.is_private:
        return False
    if (await get_step(event.sender_id)) != states.STEP_CRYPTO_USDT_BEP20_2:
        return False
    msg = event.message.message
    if not msg:
        return False
    return not _is_nav_command(msg)


@bot_is_offline
async def crypto_payments_usdt_bep20_handler(event: Message):
    msg = event.message.message
    if msg.isdigit():
        await create_crypto_invoice(event, arz="usdt-bep20", amount_irt=int(msg))
        raise events.StopPropagation
    await respond_deposit_numeric_error(
        event,
        text_key="crypto_numeric_error",
        default=texts.CRYPTO_NUMERIC_ERROR_DEFAULT,
    )
    raise events.StopPropagation


async def crypto_payment_pol_step_filter(event):
    if event.is_channel or not event.is_private:
        return False
    if (await get_step(event.sender_id)) != states.STEP_CRYPTO_POL_2:
        return False
    msg = event.message.message
    if not msg:
        return False
    return not _is_nav_command(msg)


@bot_is_offline
async def crypto_payments_pol_handler(event: Message):
    msg = event.message.message
    if msg.isdigit():
        await create_crypto_invoice(event, arz="pol", amount_irt=int(msg))
        raise events.StopPropagation
    await respond_deposit_numeric_error(
        event,
        text_key="crypto_numeric_error",
        default=texts.CRYPTO_NUMERIC_ERROR_DEFAULT,
    )
    raise events.StopPropagation


async def stars_payment_step_filter(event):
    if event.is_channel or not event.is_private:
        return False
    if (await get_step(event.sender_id)) != states.STEP_STARS_2:
        return False
    msg = event.message.message
    if not msg:
        return False
    return not _is_nav_command(msg)


@bot_is_offline
async def stars_payment_2_handler(event: Message):
    msg = event.message.message

    if msg.isdigit():
        settings = await SettingsManager().get_settings()
        amount = int(msg)
        if amount < settings.crypto_deposit_min or amount > settings.crypto_deposit_max:
            await respond_deposit_amount_range_error(
                event,
                text_key="stars_amount_range_error",
                default=texts.STARS_AMOUNT_RANGE_ERROR_DEFAULT,
                min_amount=settings.crypto_deposit_min,
                max_amount=settings.crypto_deposit_max,
            )
            raise events.StopPropagation
        await send_star_invoice(event.sender_id, amount)
        await set_step(event.sender_id, states.STEP_HOME)
        raise events.StopPropagation
    await respond_deposit_numeric_error(
        event,
        text_key="stars_numeric_error",
        default=texts.STARS_NUMERIC_ERROR_DEFAULT,
    )
    raise events.StopPropagation


async def balance_phone_verify_filter(event: Message) -> bool:
    if event.is_channel or not event.is_private:
        return False
    if not event.message.contact:
        return False
    return await get_step(event.sender_id) == states.STEP_CONF_NUMBER


@bot_is_offline
async def balance_phone_verify_handler(event: Message):
    contact = event.message.contact
    user_id = event.sender_id
    info = await UserCRUD().read_user(user_id)
    lang = info.language if info and info.language else "fa"
    user = await event.get_sender()
    username = user.username if user.username else texts.DEFAULT_USERNAME
    full_name = f"{user.first_name} {user.last_name or ''}".strip()
    phone_number = contact.phone_number

    if contact.user_id != user_id:
        await event.respond(texts.PHONE_VERIFY_WRONG_USER)
        log_message = (
            f"❌ شماره تایید نشد\n\n"
            f"▪️ آیدی عددی : {user_id}\n"
            f"❕ نام پروفایل : {full_name}\n"
            f"☎️ یوزرنیم : @{username}\n"
            f"☎️ شماره تلفن : {phone_number}"
        )
        await send_log_message(LogType.OTHER, message=log_message)
        raise events.StopPropagation

    if phone_number.startswith("+98") or phone_number.startswith("98"):
        log_message = (
            f"🔐 احراز هویت جدیدی انجام شد.\n\n"
            f"▪️ آیدی عددی : {user_id}\n"
            f"❕ نام پروفایل : {full_name}\n"
            f"☎️ یوزرنیم : @{username}\n"
            f"☎️ شماره تلفن : {phone_number}"
        )
        await send_log_message(LogType.OTHER, message=log_message)

        success = await UserCRUD().update_user(user_id=user_id, number=phone_number)
        if success:
            await event.respond(texts.PHONE_VERIFY_SUCCESS, buttons=await bhome_buttons(user_id, lang))
            await set_step(user_id=user_id, step=states.STEP_START)
        else:
            await event.respond(texts.PHONE_VERIFY_UPDATE_ERROR)
            log_message = (
                f"⛔ خطا\n\n"
                f"▪️ آیدی عددی : {user_id}\n"
                f"❕ نام پروفایل : {full_name}\n"
                f"☎️ یوزرنیم : @{username}\n"
                f"☎️ شماره تلفن : {phone_number}\n\n"
                f"{texts.PHONE_VERIFY_UPDATE_ERROR}"
            )
            await send_log_message(LogType.OTHER, message=log_message)
    else:
        await event.respond(texts.PHONE_VERIFY_INVALID_PREFIX)
        log_message = (
            f"❌ شماره تایید نشد\n\n"
            f"▪️ آیدی عددی : {user_id}\n"
            f"❕ نام پروفایل : {full_name}\n"
            f"☎️ یوزرنیم : @{username}\n"
            f"☎️ شماره تلفن : {phone_number}"
        )
        await send_log_message(LogType.OTHER, message=log_message)

    raise events.StopPropagation


def register(client):
    client.add_event_handler(
        menu_add_balance_handler,
        events.NewMessage(incoming=True, func=menu_add_balance_filter),
    )
    client.add_event_handler(
        cart_b_cart_amount_handler,
        events.NewMessage(incoming=True, func=manual_card_step_filter),
    )
    client.add_event_handler(
        balance_cancel_legacy_text_handler,
        events.NewMessage(incoming=True, func=balance_cancel_legacy_text_filter),
    )
    client.add_event_handler(
        mablagh_sharj_handler,
        events.NewMessage(incoming=True, func=receipt_photo_filter),
    )
    client.add_event_handler(
        crypto_payments_trx_handler,
        events.NewMessage(incoming=True, func=crypto_payment_trx_step_filter),
    )
    client.add_event_handler(
        crypto_payments_usdt_handler,
        events.NewMessage(incoming=True, func=crypto_payment_usdt_step_filter),
    )
    client.add_event_handler(
        crypto_payments_ton_handler,
        events.NewMessage(incoming=True, func=crypto_payment_ton_step_filter),
    )
    client.add_event_handler(
        crypto_payments_usdt_ton_handler,
        events.NewMessage(incoming=True, func=crypto_payment_usdt_ton_step_filter),
    )
    client.add_event_handler(
        crypto_payments_usdt_bep20_handler,
        events.NewMessage(incoming=True, func=crypto_payment_usdt_bep20_step_filter),
    )
    client.add_event_handler(
        crypto_payments_pol_handler,
        events.NewMessage(incoming=True, func=crypto_payment_pol_step_filter),
    )
    client.add_event_handler(
        stars_payment_2_handler,
        events.NewMessage(incoming=True, func=stars_payment_step_filter),
    )
    client.add_event_handler(
        balance_phone_verify_handler,
        events.NewMessage(incoming=True, func=balance_phone_verify_filter),
    )
