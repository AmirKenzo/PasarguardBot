"""Validation of the add-on plan lists in the panel settings API payloads."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.panel.panels import PanelSettingsResponse, PanelSettingsSaveRequest


def test_plan_lists_are_optional_so_older_clients_keep_working():
    request = PanelSettingsSaveRequest(code=1)

    assert request.volume_plans is None
    assert request.time_plans is None


def test_new_plan_may_omit_its_id():
    request = PanelSettingsSaveRequest(
        code=1,
        volume_plans=[{"storage_gb": 2.5, "price": 0}],
        time_plans=[{"id": 4, "duration_days": 30, "price": 40_000}],
    )

    assert request.volume_plans[0].id is None
    assert request.time_plans[0].id == 4


@pytest.mark.parametrize(
    "plan",
    [
        {"storage_gb": 0, "price": 1_000},
        {"storage_gb": -5, "price": 1_000},
        {"storage_gb": 10, "price": -1},
        {"id": 0, "storage_gb": 10, "price": 1_000},
    ],
    ids=["zero-size", "negative-size", "negative-price", "zero-id"],
)
def test_invalid_volume_plan_is_rejected(plan: dict):
    with pytest.raises(ValidationError):
        PanelSettingsSaveRequest(code=1, volume_plans=[plan])


@pytest.mark.parametrize(
    "plan",
    [{"duration_days": 0, "price": 1_000}, {"duration_days": 1.5, "price": 1_000}],
    ids=["zero-days", "fractional-days"],
)
def test_invalid_time_plan_is_rejected(plan: dict):
    with pytest.raises(ValidationError):
        PanelSettingsSaveRequest(code=1, time_plans=[plan])


def test_more_than_fifty_plans_is_rejected():
    plans = [{"storage_gb": size, "price": 1} for size in range(1, 52)]

    with pytest.raises(ValidationError):
        PanelSettingsSaveRequest(code=1, volume_plans=plans)


def test_settings_response_defaults_to_empty_plan_lists():
    response = PanelSettingsResponse(code=1)

    assert response.volume_plans == []
    assert response.time_plans == []
