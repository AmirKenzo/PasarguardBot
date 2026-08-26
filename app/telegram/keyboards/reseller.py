"""Reseller inline buttons with admin-customizable text and style."""

from app.db.crud.keyboards import KeyboardButtonCRUD

from .common import _get_keyboard_button_config, styled_callback_button
from .registry import KEYBOARD_BUTTON_DEFAULTS

# Shared with shop buy / renew flows (single DB record per action)
_KEY_DISCOUNT = "in.buy.discount"
_KEY_CANCEL = "in.buy.cancel"
_KEY_BACK = "in.buy.back"
_KEY_BUY_CONFIRM = "in.buy.confirm"
_KEY_RENEW_CONFIRM = "in.ms.renew.confirm"
_KEY_PAGE_PREV = "in.ms.sub_links.prev"
_KEY_PAGE_NEXT = "in.ms.sub_links.next"


async def _rs_inline_button(button_key: str, data):
    keyboard_crud = KeyboardButtonCRUD()
    text, style = await _get_keyboard_button_config(
        keyboard_crud,
        button_key,
        KEYBOARD_BUTTON_DEFAULTS[button_key],
    )
    return styled_callback_button(text, data, style)


async def rs_show_creds_button(account_code: int):
    return await _rs_inline_button("in.rs.show_creds", f"ResellerAccount_creds:{account_code}")


async def rs_change_password_button(account_code: int):
    return await _rs_inline_button("in.rs.change_password", f"ResellerAccount_chpwd:{account_code}")


async def rs_resume_button(account_code: int):
    return await _rs_inline_button("in.rs.resume", f"ResellerAccount_resume:{account_code}")


async def rs_pause_button(account_code: int):
    return await _rs_inline_button("in.rs.pause", f"ResellerAccount_pause:{account_code}")


async def rs_renew_button(account_code: int):
    return await _rs_inline_button("in.rs.renew", f"ResellerAccount_renew:{account_code}")


async def rs_usage_report_button(account_code: int):
    return await _rs_inline_button("in.rs.usage_report", f"ResellerAccount_usage:{account_code}:0")


async def rs_usage_cap_button(account_code: int):
    return await _rs_inline_button("in.rs.usage_cap", f"ResellerAccount_usage_cap:{account_code}")


async def rs_usage_cap_set_button(account_code: int):
    return await _rs_inline_button("in.rs.usage_cap_set", f"ResellerAccount_usage_cap_set:{account_code}")


async def rs_usage_cap_clear_button(account_code: int):
    return await _rs_inline_button("in.rs.usage_cap_clear", f"ResellerAccount_usage_cap_clear:{account_code}")


async def rs_buy_capacity_button(account_code: int):
    return await _rs_inline_button("in.rs.buy_user_capacity", f"ResellerAccount_capacity:{account_code}")


async def rs_capacity_confirm_button(account_code: int):
    return await _rs_inline_button(_KEY_BUY_CONFIRM, f"ResellerAccount_capacity_confirm:{account_code}")


async def rs_capacity_cancel_button(account_code: int):
    return await _rs_inline_button(_KEY_CANCEL, f"ResellerAccount_capacity_cancel:{account_code}")


async def rs_capacity_back_button(account_code: int):
    return await _rs_inline_button(_KEY_BACK, f"ResellerAccount_capacity:{account_code}")


async def rs_delete_button(account_code: int):
    return await _rs_inline_button("in.rs.delete", f"ResellerAccount_delete:{account_code}")


async def rs_back_list_button():
    return await _rs_inline_button(_KEY_BACK, "ResellerMy_list")


async def rs_buy_cancel_button():
    return await _rs_inline_button(_KEY_CANCEL, "ResellerBuy_cancel")


async def rs_buy_confirm_button():
    return await _rs_inline_button(_KEY_BUY_CONFIRM, "ResellerBuy_confirm")


async def rs_buy_discount_button():
    return await _rs_inline_button(_KEY_DISCOUNT, "ResellerBuy_apply_discount")


async def rs_buy_back_button(data: str):
    return await _rs_inline_button(_KEY_BACK, data)


async def rs_buy_random_username_button():
    return await _rs_inline_button("in.rs.buy_random_username", "ResellerBuy_random_username")


async def rs_renew_discount_button(account_code: int, plan_id: int):
    return await _rs_inline_button(_KEY_DISCOUNT, f"ResellerAccount_renew_discount:{account_code}:{plan_id}")


async def rs_renew_confirm_button(account_code: int, plan_id: int):
    return await _rs_inline_button(_KEY_RENEW_CONFIRM, f"ResellerAccount_renew_confirm:{account_code}:{plan_id}")


async def rs_renew_back_button(account_code: int):
    return await _rs_inline_button(_KEY_BACK, f"ResellerAccount_renew:{account_code}")


async def rs_delete_confirm_button(account_code: int):
    return await _rs_inline_button("in.rs.delete_confirm", f"ResellerAccount_delete_confirm:{account_code}")


async def rs_delete_cancel_button(account_code: int):
    return await _rs_inline_button(_KEY_CANCEL, f"ResellerAccount_view:{account_code}")


async def rs_chpwd_confirm_button(account_code: int):
    return await _rs_inline_button("in.rs.chpwd_confirm", f"ResellerAccount_chpwd_confirm:{account_code}")


async def rs_chpwd_cancel_button(account_code: int):
    return await _rs_inline_button(_KEY_CANCEL, f"ResellerAccount_view:{account_code}")


async def rs_usage_prev_button(account_code: int, page: int):
    return await _rs_inline_button(_KEY_PAGE_PREV, f"ResellerAccount_usage:{account_code}:{page - 1}")


async def rs_usage_next_button(account_code: int, page: int):
    return await _rs_inline_button(_KEY_PAGE_NEXT, f"ResellerAccount_usage:{account_code}:{page + 1}")


async def rs_usage_back_button(account_code: int):
    return await _rs_inline_button(_KEY_BACK, f"ResellerAccount_view:{account_code}")
