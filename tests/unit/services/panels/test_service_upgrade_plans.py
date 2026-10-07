"""Extra-volume / extra-time plan lists saved from the web panel.

The panel replaces a whole list at once; plans it sends back keep their id and
the button text, style and icon set for them in the bot.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.services.panels.settings import (
    FEATURE_SERVICE_UPGRADE,
    apply_feature_settings_patch,
    panel_time_plans,
    panel_volume_plans,
    replace_service_upgrade_plans,
)


def _feature_with_plans() -> dict:
    return {
        FEATURE_SERVICE_UPGRADE: {
            "volume_plans": [
                {"id": 1, "storage_gb": 10, "price": 50_000, "display_button_text": "ده گیگ", "button_icon": "123"},
                {"id": 3, "storage_gb": 5, "price": 30_000},
            ],
            "time_plans": [{"id": 1, "duration_days": 30, "price": 40_000, "button_style": "success"}],
        }
    }


def test_existing_plan_keeps_its_id_and_bot_button_customizations():
    feature = _feature_with_plans()

    replace_service_upgrade_plans(feature, volume_plans=[{"id": 1, "storage_gb": 20, "price": 90_000}])

    (plan,) = feature[FEATURE_SERVICE_UPGRADE]["volume_plans"]
    assert plan == {
        "id": 1,
        "storage_gb": 20,
        "price": 90_000,
        "display_button_text": "ده گیگ",
        "button_icon": "123",
    }


def test_new_plan_gets_an_id_after_the_highest_existing_one():
    feature = _feature_with_plans()

    replace_service_upgrade_plans(
        feature,
        volume_plans=[
            {"id": 3, "storage_gb": 5, "price": 30_000},
            {"id": None, "storage_gb": 2.5, "price": 0},
        ],
    )

    ids = {plan["storage_gb"]: plan["id"] for plan in feature[FEATURE_SERVICE_UPGRADE]["volume_plans"]}
    assert ids == {2.5: 4, 5: 3}


def test_unknown_or_repeated_id_is_treated_as_a_new_plan():
    feature = _feature_with_plans()

    replace_service_upgrade_plans(
        feature,
        volume_plans=[
            {"id": 3, "storage_gb": 5, "price": 30_000},
            {"id": 3, "storage_gb": 6, "price": 31_000},
            {"id": 99, "storage_gb": 7, "price": 32_000},
        ],
    )

    ids = [plan["id"] for plan in feature[FEATURE_SERVICE_UPGRADE]["volume_plans"]]
    assert sorted(ids) == [3, 4, 5]


def test_plans_are_stored_sorted_by_size_and_whole_gigabytes_as_int():
    feature = {}

    replace_service_upgrade_plans(
        feature,
        volume_plans=[{"id": None, "storage_gb": 50.0, "price": 1}, {"id": None, "storage_gb": 10.0, "price": 1}],
    )

    stored = feature[FEATURE_SERVICE_UPGRADE]["volume_plans"]
    assert [plan["storage_gb"] for plan in stored] == [10, 50]
    assert all(isinstance(plan["storage_gb"], int) for plan in stored)


def test_none_leaves_that_list_untouched():
    feature = _feature_with_plans()
    time_before = list(feature[FEATURE_SERVICE_UPGRADE]["time_plans"])

    replace_service_upgrade_plans(feature, volume_plans=[], time_plans=None)

    assert "volume_plans" not in feature[FEATURE_SERVICE_UPGRADE]
    assert feature[FEATURE_SERVICE_UPGRADE]["time_plans"] == time_before


def test_emptying_both_lists_removes_the_namespace():
    feature = _feature_with_plans()

    replace_service_upgrade_plans(feature, volume_plans=[], time_plans=[])

    assert FEATURE_SERVICE_UPGRADE not in feature


def test_settings_patch_replaces_plans_and_readers_see_them():
    panel = SimpleNamespace(feature_settings=_feature_with_plans())

    feature = apply_feature_settings_patch(
        panel,
        volume_plans=[{"id": None, "storage_gb": 100, "price": 200_000}],
        time_plans=[{"id": 1, "duration_days": 60, "price": 70_000}],
    )
    updated = SimpleNamespace(feature_settings=feature)

    assert [(plan["storage_gb"], plan["price"]) for plan in panel_volume_plans(updated)] == [(100, 200_000)]
    (time_plan,) = panel_time_plans(updated)
    assert (time_plan["id"], time_plan["duration_days"], time_plan["button_style"]) == (1, 60, "success")


def test_settings_patch_without_plans_keeps_existing_plans():
    panel = SimpleNamespace(feature_settings=_feature_with_plans())

    feature = apply_feature_settings_patch(panel, sales={"shop_enabled": False})

    assert feature[FEATURE_SERVICE_UPGRADE] == _feature_with_plans()[FEATURE_SERVICE_UPGRADE]
