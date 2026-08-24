"""Buy and renewal inline buttons."""

from telethon.tl.types import KeyboardInlineButtonRow, ReplyInlineMarkup

from app.db.crud.keyboards import KeyboardButtonCRUD

from .common import _get_keyboard_button_config, styled_callback_button
from .registry import KEYBOARD_BUTTON_DEFAULT_STYLES, KEYBOARD_BUTTON_DEFAULTS


async def _buy_inline_button(button_key: str, data):
    keyboard_crud = KeyboardButtonCRUD()
    default_style, default_icon = KEYBOARD_BUTTON_DEFAULT_STYLES.get(button_key, (None, None))
    text, style = await _get_keyboard_button_config(
        keyboard_crud,
        button_key,
        KEYBOARD_BUTTON_DEFAULTS[button_key],
        default_style=default_style,
        default_icon=default_icon,
    )
    return styled_callback_button(text, data, style)


async def buy_cancel_button(data="DataCancel"):
    return await _buy_inline_button("in.buy.cancel", data)


async def buy_back_button(data):
    return await _buy_inline_button("in.buy.back", data)


async def buy_confirm_button(data):
    return await _buy_inline_button("in.buy.confirm", data)


async def buy_discount_button(data):
    return await _buy_inline_button("in.buy.discount", data)


async def buy_default_username_button(data=b"generate_username"):
    return await _buy_inline_button("in.buy.default_username", data)


async def buy_retry_username_button(data=b"retry_buy_username"):
    return await _buy_inline_button("in.buy.retry_username", data)


async def buy_custom_button(data):
    return await _buy_inline_button("in.buy.custom", data)


async def buy_empty_list_button():
    return await _buy_inline_button("in.buy.empty_list", "backtopanels")


async def _ms_flow_styled_button(button_key: str, data, *, default_text: str | None = None):
    """English docstring for _ms_flow_styled_button."""
    keyboard_crud = KeyboardButtonCRUD()
    text, style_obj = await _get_keyboard_button_config(
        keyboard_crud,
        button_key,
        default_text or KEYBOARD_BUTTON_DEFAULTS.get(button_key, button_key),
    )
    return styled_callback_button(text, data, style_obj)


async def ms_renew_discount_button(data="ApplyCodeTakhfifTamdid"):
    return await _ms_flow_styled_button("in.ms.renew.discount", data)


async def ms_renew_back_button(data):
    return await _ms_flow_styled_button("in.ms.renew.back", data)


async def ms_renew_confirm_button(data):
    return await _ms_flow_styled_button("in.ms.renew.confirm", data)


async def ms_sub_links_prev_button(service_code: str, current_page: int):
    return await _ms_flow_styled_button(
        "in.ms.sub_links.prev",
        f"PrevSubLinks:{service_code}:{current_page}",
    )


async def ms_sub_links_next_button(service_code: str, current_page: int):
    return await _ms_flow_styled_button(
        "in.ms.sub_links.next",
        f"NextSubLinks:{service_code}:{current_page}",
    )


async def ms_sub_links_get_all_button(service_code: str):
    return await _ms_flow_styled_button("in.ms.sub_links.get_all", f"get_single_links:{service_code}")


async def ms_sub_links_back_button(data: str):
    return await _ms_flow_styled_button("in.ms.sub_links.back", data)


async def build_ms_renew_confirm_button_rows(
    *,
    confirm_data,
    back_data,
    discount_data="ApplyCodeTakhfifTamdid",
) -> ReplyInlineMarkup:
    """English docstring for build_ms_renew_confirm_button_rows."""
    return ReplyInlineMarkup(
        [
            KeyboardInlineButtonRow([await ms_renew_discount_button(discount_data)]),
            KeyboardInlineButtonRow(
                [
                    await ms_renew_back_button(back_data),
                    await ms_renew_confirm_button(confirm_data),
                ]
            ),
        ]
    )


async def build_buy_service_selection_rows(service_buttons: list, *, columns: int = 2) -> list:
    """English docstring for build_buy_service_selection_rows."""
    rows = [service_buttons[i : i + columns] for i in range(0, len(service_buttons), columns)]
    rows.append([await buy_cancel_button("DataCancel")])
    return rows


async def build_buy_confirm_button_rows(
    *,
    confirm_data,
    cancel_data="DataCancel",
    discount_data="ApplyCodeTakhfif",
    with_discount: bool = True,
) -> list:
    rows = []
    if with_discount:
        rows.append([await buy_discount_button(discount_data)])
    rows.append([await buy_cancel_button(cancel_data), await buy_confirm_button(confirm_data)])
    return rows


async def build_buy_username_prompt_rows() -> list:
    return [
        [await buy_default_username_button(b"generate_username")],
        [await buy_cancel_button(b"DataCancel")],
    ]
