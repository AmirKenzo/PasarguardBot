"""An install as it was before the reseller plan update, and the two migrations that upgrade it.

``build_old_install`` creates the tables the way they were before migrations ``a5e2c7f9d3b1``
(``reseller_accounts.billed_traffic``) and ``c8d4f2a6e9b3`` (plan add-on prices and
``reseller_accounts.extra_users``) and fills them with rows an existing install really has.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest
import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models.panels import Panels
from app.db.models.reseller_accounts import ResellerAccount
from app.db.models.reseller_billing_snapshots import ResellerBillingSnapshot
from app.db.models.reseller_events import ResellerEvent
from app.db.models.reseller_plans import ResellerPlan
from app.db.models.user import User

GB = 1024**3
DAY = 86_400
NOW = 1_800_000_000
OWNER_ID = 7
OWNER_BALANCE = 1_000_000

NEW_PLAN_COLUMNS = ("addon_day_price", "addon_gb_price", "addon_user_price")
NEW_ACCOUNT_COLUMNS = ("billed_traffic", "extra_users")
NEW_COLUMNS = {"reseller_plans": NEW_PLAN_COLUMNS, "reseller_accounts": NEW_ACCOUNT_COLUMNS}
TABLES = ("user", "panels", "reseller_plans", "reseller_accounts", "reseller_billing_snapshots")
PRIMARY_KEYS = {
    "user": "id",
    "panels": "code",
    "reseller_plans": "id",
    "reseller_accounts": "code",
    "reseller_billing_snapshots": "id",
}

_ROOT = Path(__file__).resolve().parents[3]
_VERSIONS = _ROOT / "app" / "db" / "migrations" / "versions"
MIGRATION_FILES = {
    "a5e2c7f9d3b1": "a5e2c7f9d3b1_add_reseller_billed_traffic.py",
    "c8d4f2a6e9b3": "c8d4f2a6e9b3_add_reseller_plan_addons.py",
}

# --- panels: the old panel-wide extra-user price lived in feature_settings -----------------------
_CAP = "reseller_user_capacity"
PANEL_FEATURE_SETTINGS: dict[int, str] = {
    1: json.dumps({_CAP: {"enabled": True, "price_per_user": 5000}}),  # capacity sold at 5,000
    2: json.dumps({_CAP: {"enabled": False, "price_per_user": 9000}}),  # switched off
    3: json.dumps({}),  # never configured
    4: "not json{",  # garbage left by a manual edit
    5: json.dumps({_CAP: {"enabled": True, "price_per_user": "abc"}}),  # non-numeric price
    6: json.dumps({_CAP: {"enabled": True, "price_per_user": -300}}),  # negative price
    7: json.dumps([1, 2]),  # valid JSON, wrong shape
    8: json.dumps({_CAP: {"enabled": True, "price_per_user": "7000"}}),  # numeric string
}
# What each panel's plans must carry as ``addon_user_price`` after c8d4f2a6e9b3.
PANEL_USER_PRICE = {1: 5000, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0, 8: 7000}

# --- plans --------------------------------------------------------------------------------------
P_FIXED = 1  # fixed, 50 GB / 30 days / 10 users
P_LEGACY_UNLIMITED_FIXED = 2  # fixed with data_limit 0 (created before volume was required)
P_PER_GB = 3  # legacy per_gb with a duration
P_HOURLY = 4  # old hourly plan whose price was a setup fee equal to unit_price
P_USAGE = 5  # usage, 1,500 per GB
P_FIXED_PANEL2 = 6
P_USAGE_PANEL4 = 7
P_FIXED_PANEL3 = 8
P_FIXED_PANEL5 = 9
P_FIXED_PANEL6 = 10
P_FIXED_PANEL7 = 11
P_FIXED_PANEL8 = 12
DELETED_PLAN_ID = 99

FIXED_PRICE = 100_000
LEGACY_FIXED_PRICE = 80_000
USAGE_RATE = 1_500
HOURLY_RATE = 3_000


def _plan(plan_id: int, panel: int, mode: str, **values: Any) -> dict[str, Any]:
    row = {"id": plan_id, "panel_code": panel, "pricing_mode": mode, "role_id": 1, "role_name": "reseller"}
    row.update(values)
    return row


OLD_PLANS = [
    _plan(P_FIXED, 1, "fixed", price=FIXED_PRICE, data_limit=50 * GB, duration=30, max_users=10),
    _plan(P_LEGACY_UNLIMITED_FIXED, 1, "fixed", price=LEGACY_FIXED_PRICE, data_limit=0, duration=30, max_users=5),
    _plan(P_PER_GB, 1, "per_gb", unit_price=2000, min_volume=10, max_volume=500, volume_step=10, duration=30),
    _plan(P_HOURLY, 1, "hourly", price=HOURLY_RATE, unit_price=HOURLY_RATE, max_users=20),
    _plan(P_USAGE, 1, "usage", unit_price=USAGE_RATE, max_users=15),
    _plan(P_FIXED_PANEL2, 2, "fixed", price=50_000, data_limit=10 * GB, duration=30, max_users=8),
    _plan(P_USAGE_PANEL4, 4, "usage", unit_price=1000),
    _plan(P_FIXED_PANEL3, 3, "fixed", price=60_000, data_limit=20 * GB, duration=30, max_users=6),
    _plan(P_FIXED_PANEL5, 5, "fixed", price=60_000, data_limit=20 * GB, duration=30, max_users=6),
    _plan(P_FIXED_PANEL6, 6, "fixed", price=60_000, data_limit=20 * GB, duration=30, max_users=6),
    _plan(P_FIXED_PANEL7, 7, "fixed", price=60_000, data_limit=20 * GB, duration=30, max_users=6),
    _plan(P_FIXED_PANEL8, 8, "fixed", price=60_000, data_limit=20 * GB, duration=30, max_users=6, enable=False),
]

# --- accounts -----------------------------------------------------------------------------------
A_FIXED = 101  # fixed, active, 10 days left
A_FIXED_EXPIRED = 102  # fixed, expired 2 days ago, still in grace
A_USAGE_LEDGER = 103  # usage with several ledger rows
A_USAGE_STATE_ONLY = 104  # usage, no ledger rows, counter only in billing_state
A_USAGE_FRESH = 105  # usage, never billed
A_USAGE_GARBAGE_STATE = 106  # usage with a corrupt billing_state
A_PLAN_DELETED = 107  # its plan row was deleted by the admin
A_CAPACITY_BOUGHT = 108  # max_users raised from 10 to 25 by the old capacity purchase
A_UNLIMITED_USERS = 109  # max_users 0 (unlimited)
A_HOURLY = 110
A_LEGACY_UNLIMITED = 111  # on the legacy fixed plan with data_limit 0
A_ADMIN_LOCKED = 112  # locked by an admin, expiry already passed
A_LOWERED_USERS = 113  # admin lowered max_users below the plan's
A_PER_GB = 114
A_CAPACITY_NO_PRICE = 115  # slots above the plan on a panel without a capacity price
A_FIXED_JUST_EXPIRED = 116  # active, expiry passed a minute ago (not yet processed)

USAGE_LEDGER_LATEST = 8 * GB
USAGE_STATE_COUNTER = 2 * GB


def _account(code: int, plan_id: int | None, mode: str, **values: Any) -> dict[str, Any]:
    row = {
        "code": code,
        "telegram_id": OWNER_ID,
        "panel_code": 1,
        "panel_admin_id": 1000 + code,
        "username": f"res{code}",
        "password_encrypted": "encrypted",
        "plan_id": plan_id,
        "pricing_mode": mode,
        "createtime": NOW - 60 * DAY,
        "status": "active",
    }
    row.update(values)
    return row


OLD_ACCOUNTS = [
    _account(A_FIXED, P_FIXED, "fixed", data_limit=50 * GB, max_users=10, expiration_time=NOW + 10 * DAY),
    _account(
        A_FIXED_EXPIRED,
        P_FIXED,
        "fixed",
        data_limit=50 * GB,
        max_users=10,
        expiration_time=NOW - 2 * DAY,
        status="expired",
    ),
    _account(
        A_USAGE_LEDGER,
        P_USAGE,
        "usage",
        data_limit=0,
        max_users=15,
        # An older counter in billing_state; the newest ledger row is what was last billed.
        billing_state=json.dumps(
            {"last_used_traffic": 3 * GB, "total_billed": 12_000, "usage_billed_at": NOW - 2 * DAY}
        ),
    ),
    _account(
        A_USAGE_STATE_ONLY,
        P_USAGE,
        "usage",
        max_users=15,
        billing_state=json.dumps({"last_used_traffic": USAGE_STATE_COUNTER}),
    ),
    _account(A_USAGE_FRESH, P_USAGE, "usage", max_users=15),
    _account(A_USAGE_GARBAGE_STATE, P_USAGE_PANEL4, "usage", panel_code=4, max_users=0, billing_state="not-json"),
    _account(
        A_PLAN_DELETED,
        DELETED_PLAN_ID,
        "fixed",
        data_limit=20 * GB,
        max_users=12,
        expiration_time=NOW + 20 * DAY,
    ),
    _account(A_CAPACITY_BOUGHT, P_FIXED, "fixed", data_limit=50 * GB, max_users=25, expiration_time=NOW + 5 * DAY),
    _account(A_UNLIMITED_USERS, P_FIXED, "fixed", data_limit=50 * GB, max_users=0, expiration_time=NOW + 15 * DAY),
    _account(
        A_HOURLY,
        P_HOURLY,
        "hourly",
        max_users=20,
        # Hourly accounts never had billed_traffic; the counter here must not be copied.
        billing_state=json.dumps({"last_billed_at": NOW - 3600, "last_used_traffic": 999}),
    ),
    _account(
        A_LEGACY_UNLIMITED,
        P_LEGACY_UNLIMITED_FIXED,
        "fixed",
        data_limit=0,
        max_users=5,
        expiration_time=NOW + 3 * DAY,
    ),
    _account(
        A_ADMIN_LOCKED,
        P_FIXED,
        "fixed",
        data_limit=50 * GB,
        max_users=10,
        expiration_time=NOW - DAY,
        status="admin_paused",
    ),
    _account(A_LOWERED_USERS, P_FIXED_PANEL2, "fixed", panel_code=2, data_limit=10 * GB, max_users=4),
    _account(
        A_PER_GB,
        P_PER_GB,
        "per_gb",
        data_limit=100 * GB,
        max_users=30,
        purchased_volume=100.0,
        expiration_time=NOW + 25 * DAY,
    ),
    _account(A_CAPACITY_NO_PRICE, P_FIXED_PANEL3, "fixed", panel_code=3, data_limit=20 * GB, max_users=12),
    _account(A_FIXED_JUST_EXPIRED, P_FIXED, "fixed", data_limit=50 * GB, max_users=10, expiration_time=NOW - 60),
]

# Slots the old capacity purchase gave, carried to extra_users by c8d4f2a6e9b3.
EXPECTED_EXTRA_USERS = {A_CAPACITY_BOUGHT: 15, A_CAPACITY_NO_PRICE: 6}
# Usage baselines seeded by a5e2c7f9d3b1 (latest usage ledger row, else billing_state counter).
EXPECTED_BILLED_TRAFFIC = {A_USAGE_LEDGER: USAGE_LEDGER_LATEST, A_USAGE_STATE_ONLY: USAGE_STATE_COUNTER}

OLD_SNAPSHOTS = [
    {
        "id": 1,
        "account_code": A_USAGE_LEDGER,
        "used_traffic": 5 * GB,
        "billed_amount": 7_500,
        "snapshot_at": NOW - 3 * DAY,
    },
    {
        "id": 2,
        "account_code": A_USAGE_LEDGER,
        "used_traffic": 8 * GB,
        "billed_amount": 4_500,
        "snapshot_at": NOW - 2 * DAY,
    },
    # An hourly bucket of the same account (kept from a plan change): never a usage counter.
    {
        "id": 3,
        "account_code": A_USAGE_LEDGER,
        "used_traffic": 0,
        "billed_amount": 3_000,
        "snapshot_at": NOW - DAY,
        "billed_minutes": 60,
    },
    {
        "id": 4,
        "account_code": A_HOURLY,
        "used_traffic": 0,
        "billed_amount": 3_000,
        "snapshot_at": NOW - DAY,
        "billed_minutes": 60,
    },
]


def old_metadata() -> sa.MetaData:
    """The five tables with only the columns they had before the two migrations."""
    metadata = sa.MetaData()
    for model in (User, Panels, ResellerPlan, ResellerAccount, ResellerBillingSnapshot):
        table = model.__table__
        dropped = NEW_COLUMNS.get(table.name, ())
        sa.Table(table.name, metadata, *[c._copy() for c in table.columns if c.name not in dropped])
    return metadata


def build_old_install(engine: sa.Engine) -> None:
    metadata = old_metadata()
    metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(sa.insert(metadata.tables["user"]), [{"id": OWNER_ID, "amount": OWNER_BALANCE}])
        for code, feature_settings in PANEL_FEATURE_SETTINGS.items():
            conn.execute(
                sa.text(
                    "INSERT INTO panels (code, name, enable, base_url, username, password, cookie, auth_type, "
                    "button_settings, subscription_settings, test_settings, renewal_settings, feature_settings) "
                    "VALUES (:code, :name, 1, 'https://panel.example', 'admin', 'x', '', 'password', "
                    "'{}', '{}', '{}', '{}', :features)"
                ),
                {"code": code, "name": f"panel{code}", "features": feature_settings},
            )
        # One insert per row: rows set different columns and rely on the column defaults for the rest.
        for table, rows in (
            ("reseller_plans", OLD_PLANS),
            ("reseller_accounts", OLD_ACCOUNTS),
            ("reseller_billing_snapshots", OLD_SNAPSHOTS),
        ):
            for row in rows:
                conn.execute(sa.insert(metadata.tables[table]).values(**row))


def load_migration(revision: str) -> ModuleType:
    path = _VERSIONS / MIGRATION_FILES[revision]
    spec = importlib.util.spec_from_file_location(f"upgrade_test_migration_{revision}", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_migration(engine: sa.Engine, revision: str, direction: str) -> None:
    module = load_migration(revision)
    with engine.begin() as conn, Operations.context(MigrationContext.configure(conn)):
        getattr(module, direction)()


def upgrade_all(engine: sa.Engine) -> None:
    run_migration(engine, "a5e2c7f9d3b1", "upgrade")
    run_migration(engine, "c8d4f2a6e9b3", "upgrade")


def downgrade_all(engine: sa.Engine) -> None:
    run_migration(engine, "c8d4f2a6e9b3", "downgrade")
    run_migration(engine, "a5e2c7f9d3b1", "downgrade")


def dump(engine: sa.Engine, table: str) -> dict[Any, dict[str, Any]]:
    """Every row of ``table`` keyed by its primary key."""
    with engine.connect() as conn:
        rows = conn.execute(sa.text(f'SELECT * FROM "{table}"')).mappings().all()
    return {row[PRIMARY_KEYS[table]]: dict(row) for row in rows}


def columns(engine: sa.Engine, table: str) -> list[str]:
    return [c["name"] for c in sa.inspect(engine).get_columns(table)]


def old_engine_fixture(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'old_install.db'}")
    build_old_install(engine)
    yield engine
    engine.dispose()


# --- the upgraded install, driven through the real services --------------------------------------


class FakePanelApi:
    """Pasarguard admins of the upgraded install, kept in memory."""

    def __init__(self) -> None:
        self.admins: dict[int, SimpleNamespace] = {}
        self.calls: list[tuple[str, int, dict]] = []
        self.fail_modify = False

    def add_admin(self, admin_id: int, *, data_limit: int = 0, used_traffic: int = 0, status: str = "active"):
        self.admins[admin_id] = SimpleNamespace(
            id=admin_id,
            data_limit=data_limit,
            used_traffic=used_traffic,
            permission_overrides=None,
            status=status,
        )
        return self.admins[admin_id]

    async def get_reseller_admin(self, panel, admin_id):
        return self.admins.get(admin_id)

    async def get_reseller_admins_by_id(self, panel, admin_ids):
        return {i: self.admins[i] for i in admin_ids if i in self.admins}

    async def modify_reseller_admin(self, panel, admin_id, admin):
        changes = {name: getattr(admin, name) for name in admin.model_fields_set}
        self.calls.append(("modify", admin_id, changes))
        if self.fail_modify:
            raise RuntimeError("panel unreachable")
        target = self.admins[admin_id]
        for name, value in changes.items():
            setattr(target, name, value)

    async def activate_reseller_admin(self, panel, admin_id):
        self.calls.append(("activate", admin_id, {}))
        self.admins[admin_id].status = "active"

    async def suspend_reseller_admin(self, panel, admin_id):
        self.calls.append(("suspend", admin_id, {}))
        self.admins[admin_id].status = "disabled"


def build_migrated_db(tmp_path) -> Path:
    path = tmp_path / "upgraded_install.db"
    engine = sa.create_engine(f"sqlite:///{path}")
    build_old_install(engine)
    upgrade_all(engine)
    with engine.begin() as conn:
        ResellerEvent.__table__.create(conn)
    engine.dispose()
    return path


async def upgraded_fixture(monkeypatch: pytest.MonkeyPatch, migrated_db_path: Path):
    """The upgraded install with every CRUD on it, the panel faked, logs captured and time frozen."""
    from app.db.crud import (
        discount_codes,
        panels,
        reseller_accounts,
        reseller_billing_snapshots,
        reseller_events,
        reseller_plans,
        settings,
        user,
    )
    from app.jobs.reseller import billing
    from app.services.billing import reseller_renewal
    from app.services.reseller import accounts, addons, logging, usage_meter
    from app.utils.formatting import dates

    engine = create_async_engine(f"sqlite+aiosqlite:///{migrated_db_path}")
    maker = async_sessionmaker(engine, expire_on_commit=False)
    for module in (
        discount_codes,
        panels,
        reseller_accounts,
        reseller_billing_snapshots,
        reseller_events,
        reseller_plans,
        settings,
        user,
    ):
        monkeypatch.setattr(module, "Session", maker)

    api = FakePanelApi()
    for name in (
        "get_reseller_admin",
        "get_reseller_admins_by_id",
        "modify_reseller_admin",
        "activate_reseller_admin",
        "suspend_reseller_admin",
    ):
        for module in (reseller_renewal, addons, accounts, billing, usage_meter):
            if hasattr(module, name):
                monkeypatch.setattr(module, name, getattr(api, name))

    logs: list[dict] = []

    async def fake_log(title, **kwargs):
        logs.append({"title": title, **kwargs})

    notices: list[tuple[int, str]] = []

    async def fake_notify(telegram_id, text):
        notices.append((telegram_id, text))

    for module in (reseller_renewal, addons, accounts, billing, logging):
        monkeypatch.setattr(module, "send_reseller_log", fake_log)
    monkeypatch.setattr(billing, "_notify_user", fake_notify)

    real_time_date = dates.Time_Date

    def frozen_time_date(value=None):
        return real_time_date(NOW if value is None else value)

    for module in (reseller_renewal, addons, accounts, billing):
        monkeypatch.setattr(module, "Time_Date", frozen_time_date)

    yield SimpleNamespace(maker=maker, api=api, logs=logs, notices=notices)
    await engine.dispose()
