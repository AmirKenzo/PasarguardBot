"""Which reseller actions are offered/allowed, shared by the bot keyboard and every API."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.reseller import accounts
from app.services.reseller.accounts import (
    ACTION_BUY_CAPACITY,
    ACTION_CHANGE_PASSWORD,
    ACTION_CREDENTIALS,
    ACTION_DELETE,
    ACTION_PAUSE,
    ACTION_RENEW,
    ACTION_RESUME,
    ACTION_USAGE_CAP,
    ACTION_USAGE_REPORT,
    account_actions,
)


def _account(status: str = "active", mode: str = "usage") -> SimpleNamespace:
    return SimpleNamespace(status=status, pricing_mode=mode)


@pytest.fixture
def buttons(monkeypatch):
    """Per-panel reseller button toggles; every button on unless a test turns it off."""
    state: dict[str, bool] = {}
    monkeypatch.setattr(accounts, "panel_reseller_button_enabled", lambda panel, key: state.get(key, True))
    monkeypatch.setattr(accounts, "panel_reseller_capacity_enabled", lambda panel: True)
    return state


def test_active_usage_account_gets_every_usage_action(buttons):
    actions = account_actions(_account(), panel=object())
    assert actions == {
        ACTION_CREDENTIALS,
        ACTION_CHANGE_PASSWORD,
        ACTION_PAUSE,
        ACTION_USAGE_REPORT,
        ACTION_USAGE_CAP,
        ACTION_BUY_CAPACITY,
        ACTION_DELETE,
    }


def test_paused_account_offers_resume_not_pause(buttons):
    actions = account_actions(_account(status="paused"), panel=object())
    assert ACTION_RESUME in actions
    assert ACTION_PAUSE not in actions


def test_only_fixed_plans_can_renew(buttons):
    assert ACTION_RENEW in account_actions(_account(mode="fixed"), panel=object())
    assert ACTION_RENEW not in account_actions(_account(mode="hourly"), panel=object())


def test_admin_locked_account_can_only_be_deleted(buttons):
    assert account_actions(_account(status="admin_paused"), panel=object()) == {ACTION_DELETE}


def test_disabled_panel_button_removes_the_action(buttons):
    buttons["delete"] = False
    buttons["credentials"] = False
    actions = account_actions(_account(), panel=object())
    assert ACTION_DELETE not in actions
    assert ACTION_CREDENTIALS not in actions


def test_bot_handlers_import_the_shared_service():
    # Guards against circular imports between the services and the Telegram layer.
    from app.telegram.admin.manage_user import callbacks as admin_callbacks
    from app.telegram.user.reseller import callbacks as user_callbacks

    assert user_callbacks.pause_account is accounts.pause_account
    assert admin_callbacks.delete_account is accounts.delete_account
