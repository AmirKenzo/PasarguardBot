"""Admin-only account actions: free extension and the user limit."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.reseller import accounts

NOW = 1_000_000
DAY = 86400


def _account(**overrides) -> SimpleNamespace:
    values = {
        "code": 5,
        "telegram_id": 7,
        "panel_code": 1,
        "panel_admin_id": 42,
        "username": "res",
        "status": "active",
        "expiration_time": NOW + DAY,
        "max_users": 3,
        "plan_id": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.fixture
def env(monkeypatch):
    state = {"activated": [], "updates": [], "clock_resets": [], "events": [], "sync": (True, None)}

    class Panels:
        async def get_panel_by_code(self, code):
            return SimpleNamespace(code=code)

    class Accounts:
        async def update_account(self, code, **columns):
            state["updates"].append((code, columns))

        async def reset_billing_clock(self, code, **columns):
            state["clock_resets"].append((code, columns))

    async def activate(panel, admin_id):
        state["activated"].append(admin_id)

    async def log(*args, event=None, data=None, **kwargs):
        state["events"].append((event, data))

    async def sync(account, max_users):
        return state["sync"]

    monkeypatch.setattr(accounts, "PanelsManager", Panels)
    monkeypatch.setattr(accounts, "ResellerAccountCRUD", Accounts)
    monkeypatch.setattr(accounts, "activate_reseller_admin", activate)
    monkeypatch.setattr(accounts, "send_reseller_log", log)
    monkeypatch.setattr(accounts, "sync_reseller_max_users", sync)
    monkeypatch.setattr(accounts, "Time_Date", lambda: {"stamp": NOW})
    return state


async def test_extend_adds_days_to_a_future_expiry(env):
    ok, _ = await accounts.extend_account_by_admin(_account(), days=10)
    assert ok
    assert env["updates"] == [(5, {"expiration_time": NOW + DAY + 10 * DAY})]
    assert env["activated"] == []


async def test_extend_counts_from_now_and_reactivates_an_expired_account(env):
    ok, _ = await accounts.extend_account_by_admin(_account(status="expired", expiration_time=NOW - 3 * DAY), days=5)
    assert ok
    assert env["activated"] == [42]
    assert env["clock_resets"] == [(5, {"status": "active", "expiration_time": NOW + 5 * DAY})]
    assert env["events"][0][1]["reactivated"] is True


async def test_extend_never_gives_an_unlimited_account_an_expiry(env):
    ok, _ = await accounts.extend_account_by_admin(_account(expiration_time=None), days=5)
    assert not ok
    assert env["updates"] == [] and env["clock_resets"] == []


async def test_max_users_writes_db_only_after_the_panel_accepts(env):
    env["sync"] = (False, "panel down")
    ok, message = await accounts.set_max_users_by_admin(_account(), max_users=10)
    assert (ok, message) == (False, "panel down")
    assert env["updates"] == []

    env["sync"] = (True, None)
    ok, _ = await accounts.set_max_users_by_admin(_account(), max_users=0)
    assert ok
    assert env["updates"] == [(5, {"max_users": None, "extra_users": None})]
    assert env["events"] == [("max_users", {"limit_before": 3, "limit_after": 0})]


async def test_unchanged_max_users_is_a_no_op(env):
    ok, _ = await accounts.set_max_users_by_admin(_account(), max_users=3)
    assert ok
    assert env["updates"] == [] and env["events"] == []
