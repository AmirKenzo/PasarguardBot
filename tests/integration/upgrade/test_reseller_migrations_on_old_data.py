"""Migrations a5e2c7f9d3b1 + c8d4f2a6e9b3 on an install that already has resellers.

They only add columns and carry over values the old install already had: the billed usage counter,
the panel-wide extra-user price and the slots bought with it. Nothing an old row holds may change,
and downgrading brings the old schema back with the same data.
"""

from __future__ import annotations

from tests.integration.upgrade.old_install import (
    A_HOURLY,
    A_USAGE_FRESH,
    A_USAGE_GARBAGE_STATE,
    EXPECTED_BILLED_TRAFFIC,
    EXPECTED_EXTRA_USERS,
    NEW_ACCOUNT_COLUMNS,
    NEW_COLUMNS,
    NEW_PLAN_COLUMNS,
    OLD_ACCOUNTS,
    OLD_PLANS,
    PANEL_USER_PRICE,
    TABLES,
    columns,
    downgrade_all,
    dump,
    run_migration,
    upgrade_all,
)


def _without_new_columns(table: str, rows: dict) -> dict:
    dropped = NEW_COLUMNS.get(table, ())
    return {key: {k: v for k, v in row.items() if k not in dropped} for key, row in rows.items()}


def test_upgrade_adds_only_the_new_columns(old_engine):
    before = {table: columns(old_engine, table) for table in TABLES}
    upgrade_all(old_engine)
    for table in TABLES:
        assert columns(old_engine, table) == before[table] + list(NEW_COLUMNS.get(table, ()))


def test_upgrade_keeps_every_old_value_of_every_row(old_engine):
    before = {table: dump(old_engine, table) for table in TABLES}
    upgrade_all(old_engine)
    for table in TABLES:
        assert _without_new_columns(table, dump(old_engine, table)) == before[table], table


def test_usage_baseline_is_seeded_from_latest_usage_ledger_row_else_billing_state(old_engine):
    upgrade_all(old_engine)
    accounts = dump(old_engine, "reseller_accounts")
    billed = {code: row["billed_traffic"] for code, row in accounts.items() if row["billed_traffic"] is not None}
    # 103: newest usage row (8 GB), not the stale 3 GB in billing_state nor the newer hourly bucket.
    # 104: no ledger rows, counter from billing_state. Everything else stays NULL.
    assert billed == EXPECTED_BILLED_TRAFFIC


def test_usage_accounts_without_history_or_with_corrupt_state_start_from_zero(old_engine):
    upgrade_all(old_engine)
    accounts = dump(old_engine, "reseller_accounts")
    assert accounts[A_USAGE_FRESH]["billed_traffic"] is None
    assert accounts[A_USAGE_GARBAGE_STATE]["billed_traffic"] is None


def test_non_usage_accounts_never_get_a_usage_baseline(old_engine):
    upgrade_all(old_engine)
    accounts = dump(old_engine, "reseller_accounts")
    # The hourly account had a last_used_traffic in billing_state; it must not be copied.
    assert accounts[A_HOURLY]["billed_traffic"] is None
    for row in OLD_ACCOUNTS:
        if row["pricing_mode"] != "usage":
            assert accounts[row["code"]]["billed_traffic"] is None, row["code"]


def test_panel_extra_user_price_moves_onto_each_plan_of_that_panel(old_engine):
    upgrade_all(old_engine)
    plans = dump(old_engine, "reseller_plans")
    for plan in OLD_PLANS:
        # Enabled panel price (also a numeric string) is copied; disabled, missing, garbage,
        # wrong-shaped, non-numeric and negative settings all leave the add-on off.
        assert plans[plan["id"]]["addon_user_price"] == PANEL_USER_PRICE[plan["panel_code"]], plan["id"]


def test_old_plans_get_no_extra_day_or_volume_price(old_engine):
    upgrade_all(old_engine)
    for plan in dump(old_engine, "reseller_plans").values():
        assert plan["addon_day_price"] == 0
        assert plan["addon_gb_price"] == 0


def test_capacity_bought_before_becomes_extra_users_and_max_users_is_unchanged(old_engine):
    before = dump(old_engine, "reseller_accounts")
    upgrade_all(old_engine)
    accounts = dump(old_engine, "reseller_accounts")
    extra = {code: row["extra_users"] for code, row in accounts.items() if row["extra_users"] is not None}
    # Only accounts above their plan's limit; unlimited (0) on either side, equal, lowered by an
    # admin, or a deleted plan all stay NULL. The slots carry over even where no price is set.
    assert extra == EXPECTED_EXTRA_USERS
    assert {c: r["max_users"] for c, r in accounts.items()} == {c: r["max_users"] for c, r in before.items()}


def test_downgrade_restores_the_old_schema_and_data(old_engine):
    schema = {table: columns(old_engine, table) for table in TABLES}
    data = {table: dump(old_engine, table) for table in TABLES}
    upgrade_all(old_engine)
    downgrade_all(old_engine)
    for table in TABLES:
        assert columns(old_engine, table) == schema[table], table
        assert dump(old_engine, table) == data[table], table


def test_each_migration_downgrades_on_its_own(old_engine):
    run_migration(old_engine, "a5e2c7f9d3b1", "upgrade")
    assert "billed_traffic" in columns(old_engine, "reseller_accounts")
    run_migration(old_engine, "c8d4f2a6e9b3", "upgrade")
    run_migration(old_engine, "c8d4f2a6e9b3", "downgrade")
    assert not set(NEW_PLAN_COLUMNS) & set(columns(old_engine, "reseller_plans"))
    assert columns(old_engine, "reseller_accounts")[-1] == "billed_traffic"
    run_migration(old_engine, "a5e2c7f9d3b1", "downgrade")
    assert not set(NEW_ACCOUNT_COLUMNS) & set(columns(old_engine, "reseller_accounts"))


def test_upgrade_after_downgrade_gives_the_same_result(old_engine):
    upgrade_all(old_engine)
    first = {table: dump(old_engine, table) for table in TABLES}
    downgrade_all(old_engine)
    upgrade_all(old_engine)
    assert {table: dump(old_engine, table) for table in TABLES} == first
