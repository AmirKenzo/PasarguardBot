"""Reseller purchase inline keyboards."""

from telethon import Button

from app.db.crud.panels import PanelsManager
from app.services.panels.settings import panel_reseller_button_enabled, panel_reseller_capacity_enabled
from app.services.reseller.capacity import CAPACITY_PRESETS
from app.telegram.keyboards import reseller as rs_buttons
from app.telegram.keyboards.common import styled_callback_button
from app.telegram.shared.keyboards.plan_buttons import resolve_plan_button_style
from app.telegram.user.reseller.helpers import format_plan_button_text, is_admin_locked


async def build_reseller_plan_buttons(plans) -> list:
    rows = []
    for plan in plans:
        text = format_plan_button_text(plan)
        style = resolve_plan_button_style(plan)
        rows.append([styled_callback_button(text, f"ResellerPlan_{plan.id}", style)])
    rows.append([await rs_buttons.rs_buy_cancel_button()])
    return rows


async def build_reseller_confirm_buttons(*, show_discount: bool = False) -> list:
    rows = []
    if show_discount:
        rows.append([await rs_buttons.rs_buy_discount_button()])
    rows.extend(
        [
            [await rs_buttons.rs_buy_confirm_button()],
            [await rs_buttons.rs_buy_back_button("ResellerBuy_back_username")],
            [await rs_buttons.rs_buy_cancel_button()],
        ]
    )
    return rows


async def build_reseller_renew_plan_buttons(account_code: int, plans) -> list:
    rows = []
    for plan in plans:
        text = format_plan_button_text(plan)
        style = resolve_plan_button_style(plan)
        rows.append([styled_callback_button(text, f"ResellerAccount_renew_plan:{account_code}:{plan.id}", style)])
    rows.append([Button.inline("🔙 بازگشت", data=f"ResellerAccount_view:{account_code}")])
    return rows


async def build_reseller_renew_confirm_buttons(account_code: int, plan_id: int) -> list:
    return [
        [await rs_buttons.rs_renew_discount_button(account_code, plan_id)],
        [await rs_buttons.rs_renew_confirm_button(account_code, plan_id)],
        [await rs_buttons.rs_renew_back_button(account_code)],
    ]


async def build_my_reseller_account_buttons(account) -> list:
    rows = []
    locked = is_admin_locked(account)
    panel = await PanelsManager().get_panel_by_code(account.panel_code)

    def enabled(key: str) -> bool:
        return panel_reseller_button_enabled(panel, key) if panel else True

    if not locked:
        if enabled("credentials"):
            rows.append([await rs_buttons.rs_show_creds_button(account.code)])
        if enabled("change_password"):
            rows.append([await rs_buttons.rs_change_password_button(account.code)])

    if not locked:
        if enabled("toggle_status"):
            if account.status == "paused":
                rows.append([await rs_buttons.rs_resume_button(account.code)])
            elif account.status in ("active", "suspended"):
                rows.append([await rs_buttons.rs_pause_button(account.code)])

        if account.pricing_mode == "fixed":
            rows.append([await rs_buttons.rs_renew_button(account.code)])

        if account.pricing_mode == "usage" and enabled("usage_report"):
            rows.append([await rs_buttons.rs_usage_report_button(account.code)])

        if account.pricing_mode == "usage" and enabled("usage_cap"):
            rows.append([await rs_buttons.rs_usage_cap_button(account.code)])

        if panel_reseller_capacity_enabled(panel) and enabled("buy_user_capacity"):
            rows.append([await rs_buttons.rs_buy_capacity_button(account.code)])

    if enabled("delete"):
        rows.append([await rs_buttons.rs_delete_button(account.code)])
    rows.append([await rs_buttons.rs_back_list_button()])
    return rows


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


async def build_capacity_preset_buttons(account_code: int) -> list:
    rows = []
    presets = list(CAPACITY_PRESETS)
    for i in range(0, len(presets), 3):
        chunk = presets[i : i + 3]
        rows.append([Button.inline(str(n), data=f"ResellerAccount_capacity_amount:{account_code}:{n}") for n in chunk])
    rows.append([Button.inline("🔢 تعداد دلخواه", data=f"ResellerAccount_capacity_custom:{account_code}")])
    rows.append([await rs_buttons.rs_buy_back_button(f"ResellerAccount_view:{account_code}")])
    return rows


async def build_capacity_confirm_buttons(account_code: int) -> list:
    return [
        [await rs_buttons.rs_capacity_confirm_button(account_code)],
        [await rs_buttons.rs_capacity_back_button(account_code)],
        [await rs_buttons.rs_capacity_cancel_button(account_code)],
    ]


async def build_my_resellers_list_buttons(accounts) -> list:
    return [
        [Button.inline(f"🏢 {acc.username} · #{acc.code}", data=f"ResellerAccount_view:{acc.code}")] for acc in accounts
    ]
