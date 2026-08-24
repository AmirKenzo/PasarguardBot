"""Keyboard builders for user balance."""

from telethon import Button
from telethon.tl.types import KeyboardInlineButtonRow, ReplyInlineMarkup

from app.telegram.keyboards.balance import balance_back_home_button, balance_send_receipt_button
from app.telegram.keyboards.common import styled_copy_button


async def balance_amount_error_rows() -> list:
    return [[await balance_back_home_button()]]


async def manual_card_channel_info_rows():
    from app.telegram.keyboards.balance import balance_flow_cancel_rows

    return [[await balance_send_receipt_button()], *(await balance_flow_cancel_rows())]


def transaction_review_buttons(tx_id: int) -> list:
    return [
        [
            Button.inline(text="✅ تایید", data=f"confirm_transaction:{tx_id}"),
            Button.inline(text="❌ ردکردن", data=f"reject_transaction:{tx_id}"),
        ]
    ]


def phone_verify_button():
    return [[Button.request_phone("ارسال شماره تلفن", resize=True, single_use=True)]]


def crypto_copy_markup(amount: str | float, wallet_address: str) -> ReplyInlineMarkup:
    from app.telegram.user.balance import texts

    amount_text = str(amount)
    wallet_text = str(wallet_address)
    return ReplyInlineMarkup(
        [
            KeyboardInlineButtonRow([styled_copy_button(texts.COPY_AMOUNT_LABEL, amount_text)]),
            KeyboardInlineButtonRow([styled_copy_button(texts.COPY_WALLET_LABEL, wallet_text)]),
        ]
    )
