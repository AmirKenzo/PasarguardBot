"""Balance and wallet inline buttons."""

from app.db.crud.keyboards import KeyboardButtonCRUD
from app.telegram.admin.settings_payment.texts import is_manual_card_visible

from .common import _get_keyboard_button_config, styled_callback_button
from .registry import KEYBOARD_BUTTON_DEFAULTS


def _bonus_label_suffix(enabled: bool, percent: int) -> str:
    if enabled and percent > 0:
        return f" 🎁 +{percent}%"
    return ""


async def _balance_inline_button(
    keyboard_crud: KeyboardButtonCRUD,
    button_key: str,
    default: str,
    data,
    *,
    bonus_enabled: bool = False,
    bonus_percent: int = 0,
):
    text, style = await _get_keyboard_button_config(keyboard_crud, button_key, default)
    text += _bonus_label_suffix(bonus_enabled, bonus_percent)
    return styled_callback_button(text, data, style)


async def create_inline_cartbcard(settings, user=None) -> list:
    keyboard_crud = KeyboardButtonCRUD()
    buttons: list[list] = []

    if settings and settings.arz_mode:
        buttons.append(
            [
                await _balance_inline_button(
                    keyboard_crud,
                    "in.balance.crypto",
                    KEYBOARD_BUTTON_DEFAULTS["in.balance.crypto"],
                    b"CryptoPayments",
                    bonus_enabled=settings.crypto_bonus_enabled,
                    bonus_percent=settings.crypto_bonus_percent,
                )
            ]
        )

    if settings and is_manual_card_visible(settings, user):
        buttons.append(
            [
                await _balance_inline_button(
                    keyboard_crud,
                    "in.balance.manual",
                    KEYBOARD_BUTTON_DEFAULTS["in.balance.manual"],
                    b"cart_payment",
                    bonus_enabled=settings.manual_bonus_enabled,
                    bonus_percent=settings.manual_bonus_percent,
                )
            ]
        )

    if not buttons:
        disabled_text, disabled_style = await _get_keyboard_button_config(
            keyboard_crud,
            "in.balance.disabled",
            KEYBOARD_BUTTON_DEFAULTS["in.balance.disabled"],
        )
        buttons.append([styled_callback_button(disabled_text, b"no_action", disabled_style)])

    referral_text, referral_style = await _get_keyboard_button_config(
        keyboard_crud,
        "in.balance.referral",
        KEYBOARD_BUTTON_DEFAULTS["in.balance.referral"],
    )
    buttons.append([styled_callback_button(referral_text, b"referral_invite_friends", referral_style)])
    buttons.append([await balance_back_home_button()])

    return buttons


async def create_inline_crypto_payment_buttons(
    *,
    has_trx: bool,
    has_usdt: bool,
    has_ton: bool,
) -> list:
    """English docstring for create_inline_crypto_payment_buttons."""
    keyboard_crud = KeyboardButtonCRUD()
    buttons: list[list] = []

    if has_trx:
        trx_text, trx_style = await _get_keyboard_button_config(
            keyboard_crud, "in.balance.trx", KEYBOARD_BUTTON_DEFAULTS["in.balance.trx"]
        )
        buttons.append([styled_callback_button(trx_text, b"CryptoPayments_TRX", trx_style)])

    if has_usdt:
        usdt_text, usdt_style = await _get_keyboard_button_config(
            keyboard_crud, "in.balance.usdt", KEYBOARD_BUTTON_DEFAULTS["in.balance.usdt"]
        )
        buttons.append([styled_callback_button(usdt_text, b"CryptoPayments_USDT", usdt_style)])

    if has_ton:
        ton_text, ton_style = await _get_keyboard_button_config(
            keyboard_crud, "in.balance.ton", KEYBOARD_BUTTON_DEFAULTS["in.balance.ton"]
        )
        buttons.append([styled_callback_button(ton_text, b"CryptoPayments_TON", ton_style)])

    back_text, back_style = await _get_keyboard_button_config(
        keyboard_crud, "in.balance.crypto_back", KEYBOARD_BUTTON_DEFAULTS["in.balance.crypto_back"]
    )
    buttons.append([styled_callback_button(back_text, b"cart_b_cart", back_style)])

    return buttons


async def balance_send_receipt_button():
    """English docstring for balance_send_receipt_button."""
    keyboard_crud = KeyboardButtonCRUD()
    text, style = await _get_keyboard_button_config(
        keyboard_crud,
        "in.balance.send_receipt",
        KEYBOARD_BUTTON_DEFAULTS["in.balance.send_receipt"],
    )
    return styled_callback_button(text, b"cart_payment_sendphoto", style)


async def balance_flow_cancel_button():
    """English docstring for balance_flow_cancel_button."""
    keyboard_crud = KeyboardButtonCRUD()
    text, style = await _get_keyboard_button_config(
        keyboard_crud,
        "in.balance.flow_cancel",
        KEYBOARD_BUTTON_DEFAULTS["in.balance.flow_cancel"],
    )
    return styled_callback_button(text, b"balance_flow_cancel", style)


async def balance_flow_cancel_rows() -> list:
    return [[await balance_flow_cancel_button()]]


async def balance_back_home_button():
    """English docstring for balance_back_home_button."""
    keyboard_crud = KeyboardButtonCRUD()
    text, style = await _get_keyboard_button_config(
        keyboard_crud,
        "in.balance.back_home",
        KEYBOARD_BUTTON_DEFAULTS["in.balance.back_home"],
    )
    return styled_callback_button(text, b"balance_return_home", style)
