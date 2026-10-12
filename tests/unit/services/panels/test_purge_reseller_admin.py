"""The panel admin is removed only after its users are gone, so no user is left orphaned."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.panels import admins

ACCOUNT = SimpleNamespace(code=5, panel_admin_id=42)
PANEL = SimpleNamespace(code=1)


@pytest.fixture
def env(monkeypatch):
    state = {"users_fail": False, "admin_fail": False, "admin_removed": False}

    async def delete_users(panel, admin_id):
        if state["users_fail"]:
            raise RuntimeError("timeout")
        return 3

    async def remove_admin(panel, admin_id):
        if state["admin_fail"]:
            raise RuntimeError("timeout")
        state["admin_removed"] = True

    monkeypatch.setattr(admins, "delete_reseller_admin_users", delete_users)
    monkeypatch.setattr(admins, "remove_reseller_admin", remove_admin)
    return state


async def test_users_and_admin_removed(env):
    assert await admins.purge_reseller_admin(PANEL, ACCOUNT) == (3, True)
    assert env["admin_removed"]


async def test_failed_user_delete_keeps_admin(env):
    env["users_fail"] = True
    assert await admins.purge_reseller_admin(PANEL, ACCOUNT) == (0, False)
    assert not env["admin_removed"]


async def test_failed_admin_removal_is_not_safe_to_drop(env):
    env["admin_fail"] = True
    assert await admins.purge_reseller_admin(PANEL, ACCOUNT) == (3, False)
