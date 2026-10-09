"""A reseller row is only dropped once its panel admin is really gone."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.reseller import accounts, panel_sync

ACCOUNT = SimpleNamespace(code=5, panel_code=1, panel_admin_id=None, username="res", telegram_id=7)


@pytest.fixture
def env(monkeypatch):
    state = {"panel": SimpleNamespace(code=1), "removed": False, "rows_deleted": [], "snapshots_deleted": []}

    class Panels:
        async def get_panel_by_code(self, code):
            return state["panel"]

    class Snapshots:
        async def delete_snapshots_for_account(self, code):
            state["snapshots_deleted"].append(code)

    class Accounts:
        async def delete_account(self, code):
            state["rows_deleted"].append(code)

    async def purge(panel, account):
        return (3, True) if state["removed"] else (0, False)

    async def no_log(*args, **kwargs):
        return None

    monkeypatch.setattr(panel_sync, "PanelsManager", Panels)
    monkeypatch.setattr(panel_sync, "ResellerBillingSnapshotCRUD", Snapshots)
    monkeypatch.setattr(panel_sync, "purge_reseller_admin", purge)
    monkeypatch.setattr(accounts, "ResellerAccountCRUD", Accounts)
    monkeypatch.setattr(accounts, "send_reseller_log", no_log)
    return state


async def test_failed_admin_removal_keeps_row_and_history(env):
    ok, _ = await accounts.delete_account(ACCOUNT)
    assert not ok
    assert env["rows_deleted"] == []
    assert env["snapshots_deleted"] == []


async def test_removed_admin_drops_row_and_history(env):
    env["removed"] = True
    ok, _ = await accounts.delete_account(ACCOUNT)
    assert ok
    assert env["rows_deleted"] == [5]
    assert env["snapshots_deleted"] == [5]


async def test_deleted_panel_lets_the_row_go(env):
    env["panel"] = None
    deleted_users, safe_to_drop = await panel_sync.purge_reseller_from_panel(ACCOUNT)
    assert (deleted_users, safe_to_drop) == (0, True)
