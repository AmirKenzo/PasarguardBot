"""Unit tests for per-panel expired-service auto-delete settings."""

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.models.panel.panels import PanelRenewalSettingsPayload
from app.services.panels.settings import (
    DEFAULT_EXPIRED_GRACE_DAYS,
    MAX_EXPIRED_GRACE_DAYS,
    MIN_EXPIRED_GRACE_DAYS,
    panel_expired_auto_delete_enabled,
    panel_expired_grace_days,
    resolve_panel_update_kwargs,
)


def test_defaults_keep_legacy_three_day_delete():
    panel = SimpleNamespace(renewal_settings=None)
    assert panel_expired_auto_delete_enabled(panel) is True
    assert panel_expired_grace_days(panel) == DEFAULT_EXPIRED_GRACE_DAYS == 3
    assert panel_expired_grace_days(None) == 3


def test_grace_days_are_clamped_and_parsed():
    assert panel_expired_grace_days(SimpleNamespace(renewal_settings={"expired_grace_days": "30"})) == 30
    assert (
        panel_expired_grace_days(SimpleNamespace(renewal_settings={"expired_grace_days": 0})) == MIN_EXPIRED_GRACE_DAYS
    )
    assert (
        panel_expired_grace_days(SimpleNamespace(renewal_settings={"expired_grace_days": 9999}))
        == MAX_EXPIRED_GRACE_DAYS
    )
    assert panel_expired_grace_days(SimpleNamespace(renewal_settings={"expired_grace_days": "x"})) == 3


def test_legacy_update_kwargs_map_into_renewal_settings():
    panel = SimpleNamespace(renewal_settings={"webhook_notifications_enabled": True})
    values = resolve_panel_update_kwargs(panel, expired_grace_days=7, expired_auto_delete_enabled=False)
    renewal = values["renewal_settings"]
    assert renewal["expired_grace_days"] == 7
    assert renewal["expired_auto_delete_enabled"] is False
    assert renewal["webhook_notifications_enabled"] is True


def test_payload_rejects_out_of_range_grace_days():
    assert PanelRenewalSettingsPayload(expired_grace_days=30).expired_grace_days == 30
    with pytest.raises(ValidationError):
        PanelRenewalSettingsPayload(expired_grace_days=0)
    with pytest.raises(ValidationError):
        PanelRenewalSettingsPayload(expired_grace_days=366)
