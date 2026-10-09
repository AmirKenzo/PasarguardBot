"""Reseller purchase inline keyboards."""

from telethon import Button

from app.db.crud.panels import PanelsManager
from app.db.crud.reseller_plans import ResellerPlanManager
from app.services.reseller.accounts import (
    ACTION_BUY_CAPACITY,
    ACTION_CHANGE_PASSWORD,
    ACTION_CREDENTIALS,
    ACTION_DELETE,
    ACTION_EXTRA_DAYS,
    ACTION_EXTRA_VOLUME,
    ACTION_PAUSE,
    ACTION_RENEW,
    ACTION_RESUME,
    ACTION_USAGE_CAP,
    ACTION_USAGE_REPORT,
    account_actions,
)
from app.telegram.keyboards import reseller as rs_buttons
from app.telegram.keyboards.common import styled_callback_button
from app.telegram.shared.keyboards.plan_buttons import resolve_plan_button_style
from app.telegram.shared.reseller_plan_guides import ADDON_PRESETS, ADDON_TOKEN_OF, ADDON_UNITS
from app.telegram.user.reseller.helpers import format_plan_button_text

ACCOUNT_MENU_ORDER: tuple[str, ...] = (
    ACTION_CREDENTIALS,
    ACTION_CHANGE_PASSWORD,
    ACTION_RESUME,
    ACTION_PAUSE,
    ACTION_RENEW,
    ACTION_EXTRA_DAYS,
    ACTION_EXTRA_VOLUME,
    ACTION_BUY_CAPACITY,
    ACTION_USAGE_REPORT,
    ACTION_USAGE_CAP,
    ACTION_DELETE,
)

_ACCOUNT_MENU_BUTTONS = {
    ACTION_CREDENTIALS: rs_buttons.rs_show_creds_button,
    ACTION_CHANGE_PASSWORD: rs_buttons.rs_change_password_button,
    ACTION_RESUME: rs_buttons.rs_resume_button,
    ACTION_PAUSE: rs_buttons.rs_pause_button,
    ACTION_RENEW: rs_buttons.rs_renew_button,
    ACTION_EXTRA_DAYS: rs_buttons.rs_extra_days_button,
    ACTION_EXTRA_VOLUME: rs_buttons.rs_extra_volume_button,
    ACTION_BUY_CAPACITY: rs_buttons.rs_buy_capacity_button,
    ACTION_USAGE_REPORT: rs_buttons.rs_usage_report_button,
    ACTION_USAGE_CAP: rs_buttons.rs_usage_cap_button,
    ACTION_DELETE: rs_buttons.rs_delete_button,
}


def account_menu_actions(actions) -> list[str]:
    """Actions to show as buttons, in menu order (resume and pause never both)."""
    ordered = [action for action in ACCOUNT_MENU_ORDER if action in actions]
    if ACTION_RESUME in ordered and ACTION_PAUSE in ordered:
        ordered.remove(ACTION_PAUSE)
    return ordered


def addon_preset_rows(account_code: int, addon: str) -> list[list[tuple[str, str]]]:
    """(label, callback data) rows of preset quantities for one add-on."""
    token = ADDON_TOKEN_OF[addon]
    unit = ADDON_UNITS[addon]
    presets = list(ADDON_PRESETS[addon])
    return [
        [(f"{n} {unit}", f"ResellerAccount_addon_amount:{account_code}:{token}:{n}") for n in presets[i : i + 3]]
        for i in range(0, len(presets), 3)
    ]


async def build_reseller_plan_buttons(plans) -> list:
    rows = []
    for plan in plans:
        text = format_plan_button_text(plan)
        style = resolve_plan_button_style(plan)
        rows.append([styled_callback_button(text, f"ResellerPlan_{plan.id}", style)])
    rows.append([await rs_buttons.rs_buy_cancel_button()])
    return rows


async def build_reseller_confirm_buttons(*, show_discount: bool = False, topup: bool = False) -> list:
    rows = []
    if show_discount:
        rows.append([await rs_buttons.rs_buy_discount_button()])
    rows.extend(
        [
            [await rs_buttons.rs_buy_confirm_button(topup=topup)],
            [Button.inline("❓ این پلن چطور کار می‌کند؟", data="ResellerBuy_guide")],
            [await rs_buttons.rs_buy_back_button("ResellerBuy_back_username")],
            [await rs_buttons.rs_buy_cancel_button()],
        ]
    )
    return rows


async def build_reseller_renew_confirm_buttons(account_code: int, plan_id: int, *, show_discount: bool = True) -> list:
    rows = []
    if show_discount:
        rows.append([await rs_buttons.rs_renew_discount_button(account_code, plan_id)])
    rows.append([await rs_buttons.rs_renew_confirm_button(account_code, plan_id)])
    rows.append([await rs_buttons.rs_renew_back_button(account_code)])
    return rows


async def load_account_context(account):
    """The account's panel and plan, which decide its buttons."""
    panel = await PanelsManager().get_panel_by_code(account.panel_code)
    plan = await ResellerPlanManager().get_plan(account.plan_id) if account.plan_id else None
    return panel, plan


async def build_my_reseller_account_buttons(account, *, panel=None, plan=None) -> list:
    if panel is None or plan is None:
        loaded_panel, loaded_plan = await load_account_context(account)
        panel = panel if panel is not None else loaded_panel
        plan = plan if plan is not None else loaded_plan
    rows = [
        [await _ACCOUNT_MENU_BUTTONS[action](account.code)]
        for action in account_menu_actions(account_actions(account, panel, plan))
    ]
    rows.append([await rs_buttons.rs_back_list_button()])
    return rows


async def build_addon_preset_buttons(account_code: int, addon: str) -> list:
    rows = [[Button.inline(label, data=data) for label, data in row] for row in addon_preset_rows(account_code, addon)]
    token = ADDON_TOKEN_OF[addon]
    rows.append([Button.inline("🔢 مقدار دلخواه", data=f"ResellerAccount_addon_custom:{account_code}:{token}")])
    rows.append([await rs_buttons.rs_account_back_button(account_code)])
    return rows


async def build_addon_confirm_buttons(account_code: int, addon: str, *, topup: bool = False) -> list:
    token = ADDON_TOKEN_OF[addon]
    return [
        [await rs_buttons.rs_addon_confirm_button(account_code, token, topup=topup)],
        [await rs_buttons.rs_addon_back_button(account_code, token)],
        [await rs_buttons.rs_addon_cancel_button(account_code)],
    ]


async def build_usage_cap_menu_buttons(account_code: int, *, has_cap: bool) -> list:
    rows = [[await rs_buttons.rs_usage_cap_set_button(account_code)]]
    if has_cap:
        rows.append([await rs_buttons.rs_usage_cap_clear_button(account_code)])
    rows.append([await rs_buttons.rs_usage_back_button(account_code)])
    return rows


async def build_password_confirm_buttons(account_code: int) -> list:
    return [
        [await rs_buttons.rs_chpwd_confirm_button(account_code)],
        [await rs_buttons.rs_chpwd_cancel_button(account_code)],
    ]


async def build_delete_confirm_buttons(account_code: int) -> list:
    return [
        [await rs_buttons.rs_delete_confirm_button(account_code)],
        [await rs_buttons.rs_delete_cancel_button(account_code)],
    ]


async def build_usage_history_buttons(account_code: int, page: int, has_prev: bool, has_next: bool) -> list:
    rows = []
    nav = []
    if has_prev:
        nav.append(await rs_buttons.rs_usage_prev_button(account_code, page))
    if has_next:
        nav.append(await rs_buttons.rs_usage_next_button(account_code, page))
    if nav:
        rows.append(nav)
    rows.append([await rs_buttons.rs_usage_back_button(account_code)])
    return rows


async def build_my_resellers_list_buttons(accounts) -> list:
    return [
        [Button.inline(f"🏢 {acc.username} · #{acc.code}", data=f"ResellerAccount_view:{acc.code}")] for acc in accounts
    ]
