"""Resellers bought before the update keep working on the upgraded database.

Each test runs the real services (renewal, add-ons, billing job, account actions) against an old
install that went through both migrations; only the Pasarguard panel and the bot are faked.
"""

from __future__ import annotations

import json

import pytest
import sqlalchemy as sa

from app.db.crud.reseller_accounts import ResellerAccountCRUD
from app.db.crud.reseller_billing_snapshots import ResellerBillingSnapshotCRUD
from app.db.crud.reseller_plans import ResellerPlanManager
from app.db.crud.user import UserCRUD
from app.jobs.reseller import billing
from app.services.billing.reseller_renewal import renew_reseller_account
from app.services.reseller import accounts as account_service
from app.services.reseller.addons import buy_addon
from app.services.reseller.capacity import increase_reseller_capacity
from app.services.reseller.plan_rules import ADDON_DAYS, ADDON_USERS
from tests.integration.upgrade.old_install import (
    A_ADMIN_LOCKED,
    A_CAPACITY_BOUGHT,
    A_FIXED,
    A_FIXED_EXPIRED,
    A_FIXED_JUST_EXPIRED,
    A_HOURLY,
    A_LEGACY_UNLIMITED,
    A_PLAN_DELETED,
    A_UNLIMITED_USERS,
    A_USAGE_FRESH,
    A_USAGE_LEDGER,
    A_USAGE_STATE_ONLY,
    DAY,
    DELETED_PLAN_ID,
    FIXED_PRICE,
    GB,
    HOURLY_RATE,
    LEGACY_FIXED_PRICE,
    NOW,
    OWNER_BALANCE,
    OWNER_ID,
    P_FIXED,
    P_LEGACY_UNLIMITED_FIXED,
    P_USAGE,
    PANEL_USER_PRICE,
    USAGE_LEDGER_LATEST,
    USAGE_RATE,
    USAGE_STATE_COUNTER,
)


async def _account(code: int):
    ok, account = await ResellerAccountCRUD().get_account(code)
    assert ok, account
    return account


async def _balance() -> int:
    return int((await UserCRUD().read_user(OWNER_ID)).amount)


async def _panel(upgraded):
    from app.db.crud.panels import PanelsManager

    return await PanelsManager().get_panel_by_code(code=1)


async def _ledger(upgraded, code: int) -> list:
    return await ResellerBillingSnapshotCRUD().get_snapshots(code)


def _admin_id(code: int) -> int:
    return 1000 + code


def _account_columns(account) -> dict:
    return {c.name: getattr(account, c.name) for c in account.__table__.columns}


# --- renewal ------------------------------------------------------------------------------------


async def test_old_fixed_account_renews_with_its_own_plan_and_pays_once(upgraded):
    upgraded.api.add_admin(_admin_id(A_FIXED), data_limit=50 * GB, used_traffic=20 * GB)
    before = await _account(A_FIXED)

    ok, message = await renew_reseller_account(A_FIXED, P_FIXED, OWNER_ID)

    assert ok, message
    after = await _account(A_FIXED)
    assert await _balance() == OWNER_BALANCE - FIXED_PRICE
    # Remaining 10 days kept, 30 added; unused 30 GB kept, 50 GB added.
    assert after.expiration_time == before.expiration_time + 30 * DAY
    assert after.data_limit == 100 * GB
    assert upgraded.api.admins[_admin_id(A_FIXED)].data_limit == 100 * GB
    assert after.max_users == before.max_users == 10
    assert after.extra_users is None
    assert (after.plan_id, after.status) == (P_FIXED, "active")


async def test_expired_old_fixed_account_in_grace_renews_from_now_and_comes_back(upgraded):
    upgraded.api.add_admin(_admin_id(A_FIXED_EXPIRED), data_limit=50 * GB, used_traffic=50 * GB, status="disabled")

    ok, message = await renew_reseller_account(A_FIXED_EXPIRED, P_FIXED, OWNER_ID)

    assert ok, message
    after = await _account(A_FIXED_EXPIRED)
    assert await _balance() == OWNER_BALANCE - FIXED_PRICE
    assert after.expiration_time == NOW + 30 * DAY
    assert after.status == "active"
    assert upgraded.api.admins[_admin_id(A_FIXED_EXPIRED)].status == "active"


async def test_old_fixed_account_cannot_renew_with_another_plan_and_is_not_charged(upgraded):
    upgraded.api.add_admin(_admin_id(A_FIXED), data_limit=50 * GB, used_traffic=20 * GB)
    before = _account_columns(await _account(A_FIXED))

    ok, _ = await renew_reseller_account(A_FIXED, P_LEGACY_UNLIMITED_FIXED, OWNER_ID)

    assert not ok
    assert await _balance() == OWNER_BALANCE
    assert _account_columns(await _account(A_FIXED)) == before
    assert upgraded.api.calls == []


async def test_old_account_on_legacy_unlimited_fixed_plan_renews_and_stays_unlimited(upgraded):
    # The panel admin is unlimited (0) and has already used far more than any plan volume.
    upgraded.api.add_admin(_admin_id(A_LEGACY_UNLIMITED), data_limit=0, used_traffic=300 * GB)
    before = await _account(A_LEGACY_UNLIMITED)

    ok, message = await renew_reseller_account(A_LEGACY_UNLIMITED, P_LEGACY_UNLIMITED_FIXED, OWNER_ID)

    assert ok, message
    after = await _account(A_LEGACY_UNLIMITED)
    assert await _balance() == OWNER_BALANCE - LEGACY_FIXED_PRICE
    assert after.expiration_time == before.expiration_time + 30 * DAY
    assert after.data_limit == 0
    assert upgraded.api.admins[_admin_id(A_LEGACY_UNLIMITED)].data_limit == 0
    assert not any("data_limit" in changes for _, _, changes in upgraded.api.calls)


# --- usage billing ------------------------------------------------------------------------------


async def test_old_usage_account_is_billed_only_for_traffic_after_the_migrated_baseline(upgraded):
    # The panel's lifetime counter is 10 GB; 8 GB were billed before the update.
    upgraded.api.add_admin(_admin_id(A_USAGE_LEDGER), used_traffic=10 * GB)
    panel = await _panel(upgraded)
    old_rows = len(await _ledger(upgraded, A_USAGE_LEDGER))

    await billing._process_usage_account(await _account(A_USAGE_LEDGER), None, NOW, panel=panel)

    assert await _balance() == OWNER_BALANCE - 2 * USAGE_RATE
    assert (await _account(A_USAGE_LEDGER)).billed_traffic == 10 * GB
    rows = await _ledger(upgraded, A_USAGE_LEDGER)
    assert len(rows) == old_rows + 1
    newest = max(rows, key=lambda r: (r.snapshot_at, r.id))
    assert (newest.used_traffic, newest.used_bytes, newest.billed_amount) == (10 * GB, 2 * GB, 2 * USAGE_RATE)


async def test_ledger_purge_after_update_does_not_rebill_old_usage(upgraded):
    admin = upgraded.api.add_admin(_admin_id(A_USAGE_LEDGER), used_traffic=10 * GB)
    panel = await _panel(upgraded)
    await billing._process_usage_account(await _account(A_USAGE_LEDGER), None, NOW, panel=panel)

    removed = await ResellerBillingSnapshotCRUD().delete_snapshots_before(NOW + 1)
    assert removed > 0 and await _ledger(upgraded, A_USAGE_LEDGER) == []

    await billing._process_usage_account(await _account(A_USAGE_LEDGER), None, NOW + 60, panel=panel)
    assert await _balance() == OWNER_BALANCE - 2 * USAGE_RATE

    admin.used_traffic = 11 * GB
    await billing._process_usage_account(await _account(A_USAGE_LEDGER), None, NOW + 120, panel=panel)
    assert await _balance() == OWNER_BALANCE - 3 * USAGE_RATE
    assert (await _account(A_USAGE_LEDGER)).billed_traffic == 11 * GB


async def test_old_usage_account_with_counter_only_in_billing_state_bills_from_that_counter(upgraded):
    upgraded.api.add_admin(_admin_id(A_USAGE_STATE_ONLY), used_traffic=USAGE_STATE_COUNTER + GB)

    await billing._process_usage_account(await _account(A_USAGE_STATE_ONLY), None, NOW, panel=await _panel(upgraded))

    assert await _balance() == OWNER_BALANCE - USAGE_RATE


async def test_old_usage_account_never_billed_is_billed_from_zero_as_before(upgraded):
    upgraded.api.add_admin(_admin_id(A_USAGE_FRESH), used_traffic=GB)

    await billing._process_usage_account(await _account(A_USAGE_FRESH), None, NOW, panel=await _panel(upgraded))

    assert await _balance() == OWNER_BALANCE - USAGE_RATE
    assert (await _account(A_USAGE_FRESH)).billed_traffic == GB


async def test_old_usage_account_without_new_traffic_is_not_charged(upgraded):
    upgraded.api.add_admin(_admin_id(A_USAGE_LEDGER), used_traffic=USAGE_LEDGER_LATEST)

    await billing._process_usage_account(await _account(A_USAGE_LEDGER), None, NOW, panel=await _panel(upgraded))

    assert await _balance() == OWNER_BALANCE
    assert (await _account(A_USAGE_LEDGER)).billed_traffic == USAGE_LEDGER_LATEST


async def test_old_hourly_plan_bills_its_hourly_rate_not_the_setup_fee_on_top(upgraded):
    await billing._process_hourly_account(await _account(A_HOURLY), None, NOW, panel=await _panel(upgraded))

    assert await _balance() == OWNER_BALANCE - HOURLY_RATE
    state = json.loads((await _account(A_HOURLY)).billing_state)
    assert state["last_billed_at"] == NOW


# --- add-ons ------------------------------------------------------------------------------------


async def test_old_capacity_slots_are_kept_and_new_extra_users_add_on_top(upgraded):
    upgraded.api.add_admin(_admin_id(A_CAPACITY_BOUGHT), data_limit=50 * GB)
    account = await _account(A_CAPACITY_BOUGHT)
    assert (account.max_users, account.extra_users) == (25, 15)

    ok, message = await increase_reseller_capacity(account, await _panel(upgraded), quantity=5, telegram_id=OWNER_ID)

    assert ok, message
    after = await _account(A_CAPACITY_BOUGHT)
    # Priced with the panel price the migration moved onto the plan.
    assert await _balance() == OWNER_BALANCE - 5 * PANEL_USER_PRICE[1]
    assert (after.max_users, after.extra_users) == (30, 20)
    assert upgraded.api.admins[_admin_id(A_CAPACITY_BOUGHT)].permission_overrides.max_users == 30


async def test_old_account_with_unlimited_users_is_not_offered_or_sold_extra_users(upgraded):
    account = await _account(A_UNLIMITED_USERS)
    plan = await ResellerPlanManager().get_plan(account.plan_id)
    panel = await _panel(upgraded)

    assert account_service.ACTION_BUY_CAPACITY not in account_service.account_actions(account, panel, plan)
    ok, _, _ = await buy_addon(account, panel, plan, ADDON_USERS, 5, telegram_id=OWNER_ID)
    assert not ok
    assert await _balance() == OWNER_BALANCE
    assert (await _account(A_UNLIMITED_USERS)).max_users == 0


async def test_add_on_purchase_refunds_the_wallet_exactly_when_the_panel_call_fails(upgraded):
    upgraded.api.add_admin(_admin_id(A_CAPACITY_BOUGHT), data_limit=50 * GB)
    upgraded.api.fail_modify = True
    before = _account_columns(await _account(A_CAPACITY_BOUGHT))

    ok, _ = await increase_reseller_capacity(
        await _account(A_CAPACITY_BOUGHT), await _panel(upgraded), quantity=3, telegram_id=OWNER_ID
    )

    assert not ok
    assert await _balance() == OWNER_BALANCE
    assert _account_columns(await _account(A_CAPACITY_BOUGHT)) == before
    assert upgraded.logs == []


# --- account whose plan was deleted -------------------------------------------------------------


async def test_account_with_deleted_plan_offers_no_add_ons_and_does_not_crash(upgraded):
    account = await _account(A_PLAN_DELETED)
    plan = await ResellerPlanManager().get_plan(account.plan_id)
    assert plan is None

    actions = account_service.account_actions(account, await _panel(upgraded), plan)

    assert (
        not {
            account_service.ACTION_EXTRA_DAYS,
            account_service.ACTION_EXTRA_VOLUME,
            account_service.ACTION_BUY_CAPACITY,
        }
        & actions
    )
    assert account_service.ACTION_CREDENTIALS in actions


async def test_account_with_deleted_plan_renew_and_add_ons_are_refused_without_charge(upgraded):
    upgraded.api.add_admin(_admin_id(A_PLAN_DELETED), data_limit=20 * GB)
    before = _account_columns(await _account(A_PLAN_DELETED))
    panel = await _panel(upgraded)

    renewed, _ = await renew_reseller_account(A_PLAN_DELETED, DELETED_PLAN_ID, OWNER_ID)
    capacity, _ = await increase_reseller_capacity(
        await _account(A_PLAN_DELETED), panel, quantity=1, telegram_id=OWNER_ID
    )
    days, _, _ = await buy_addon(await _account(A_PLAN_DELETED), panel, None, ADDON_DAYS, 1, telegram_id=OWNER_ID)

    assert (renewed, capacity, days) == (False, False, False)
    assert await _balance() == OWNER_BALANCE
    assert _account_columns(await _account(A_PLAN_DELETED)) == before
    assert upgraded.api.calls == []


# --- admin lock ---------------------------------------------------------------------------------


async def test_admin_locked_old_account_does_not_auto_expire(upgraded):
    due = {a.code for a in await ResellerAccountCRUD().get_accounts_to_expire(NOW)}

    assert A_ADMIN_LOCKED not in due
    assert A_FIXED_JUST_EXPIRED in due


async def test_admin_locked_old_account_cannot_be_renewed_or_extended_by_its_owner(upgraded):
    upgraded.api.add_admin(_admin_id(A_ADMIN_LOCKED), data_limit=50 * GB, status="disabled")
    before = _account_columns(await _account(A_ADMIN_LOCKED))
    plan = await ResellerPlanManager().get_plan(P_FIXED)

    renewed, _ = await renew_reseller_account(A_ADMIN_LOCKED, P_FIXED, OWNER_ID)
    capacity, _, _ = await buy_addon(
        await _account(A_ADMIN_LOCKED), await _panel(upgraded), plan, ADDON_USERS, 1, telegram_id=OWNER_ID
    )

    assert (renewed, capacity) == (False, False)
    assert await _balance() == OWNER_BALANCE
    assert _account_columns(await _account(A_ADMIN_LOCKED)) == before
    assert upgraded.api.calls == []


async def test_expire_job_skips_the_admin_locked_old_account(upgraded):
    upgraded.api.add_admin(_admin_id(A_FIXED_JUST_EXPIRED))
    upgraded.api.add_admin(_admin_id(A_ADMIN_LOCKED), status="disabled")

    await billing._expire_timed_accounts(NOW, None)

    assert (await _account(A_FIXED_JUST_EXPIRED)).status == "expired"
    assert (await _account(A_ADMIN_LOCKED)).status == "admin_paused"
    assert [c for c in upgraded.api.calls if c[1] == _admin_id(A_ADMIN_LOCKED)] == []


@pytest.mark.parametrize("code", [A_USAGE_LEDGER, A_HOURLY])
async def test_old_pay_as_you_go_accounts_cannot_be_renewed(upgraded, code):
    account = await _account(code)

    ok, _ = await renew_reseller_account(code, account.plan_id, OWNER_ID)

    assert not ok
    assert await _balance() == OWNER_BALANCE


async def test_upgraded_plans_load_through_the_orm_with_add_on_prices(upgraded):
    plan = await ResellerPlanManager().get_plan(P_USAGE)
    async with upgraded.maker() as session:
        count = (await session.execute(sa.text("SELECT COUNT(*) FROM reseller_plans"))).scalar_one()
    assert count > 0
    assert (plan.addon_user_price, plan.addon_day_price, plan.addon_gb_price) == (PANEL_USER_PRICE[1], 0, 0)
