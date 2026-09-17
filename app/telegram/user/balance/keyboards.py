"""Keyboard builders for user balance."""

from telethon import Button
from telethon.tl.types import KeyboardInlineButtonRow, ReplyInlineMarkup

from app.telegram.keyboards.balance import balance_back_home_button, balance_send_receipt_button
from app.telegram.keyboards.common import build_telegram_button_style, styled_copy_button, styled_url_button

_TON_BUTTON_ICON = 5305626186544599263


async def balance_amount_error_rows() -> list:
    return [[await balance_back_home_button()]]


def tonkeeper_transfer_url(wallet_address: str, amount_ton: str | float) -> str:
    """HTTPS deep link that opens Tonkeeper with destination + amount prefilled."""
    nanotons = int(float(amount_ton) * 1e9)
    return f"https://app.tonkeeper.com/transfer/{wallet_address}?amount={nanotons}"


def tonkeeper_usdt_transfer_url(wallet_address: str, amount_usdt: str | float, jetton_master: str) -> str:
    """Tonkeeper deep link for USDT (jetton) transfer on TON."""
    units = round(float(amount_usdt) * 1_000_000)
    return f"https://app.tonkeeper.com/transfer/{wallet_address}?amount={units}&jetton={jetton_master}"


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


def crypto_copy_markup(
    amount: str | float,
    wallet_address: str,
    *,
    open_url: str | None = None,
    open_label: str | None = None,
) -> ReplyInlineMarkup:
    from app.telegram.user.balance import texts

    amount_text = str(amount)
    wallet_text = str(wallet_address)
    rows = [
        KeyboardInlineButtonRow([styled_copy_button(texts.COPY_AMOUNT_LABEL, amount_text)]),
        KeyboardInlineButtonRow([styled_copy_button(texts.COPY_WALLET_LABEL, wallet_text)]),
    ]
    if open_url:
        style = build_telegram_button_style("primary", _TON_BUTTON_ICON)
        rows.append(
            KeyboardInlineButtonRow([styled_url_button(open_label or texts.OPEN_TONKEEPER_LABEL, open_url, style)])
        )
    return ReplyInlineMarkup(rows)
