"""Panel JSON settings — defaults, getters, and legacy field mapping."""

from __future__ import annotations

import copy
import json
from typing import Any

DEFAULT_BUTTON_SETTINGS: dict[str, bool] = {
    "time": True,
    "volume": True,
    "renew": True,
    "change_subscription": True,
    "other_links": True,
    "change_link": True,
    "copy_link": True,
    "qr": True,
    "transfer": True,
    "clients": True,
    "usage_chart": True,
    "info": True,
    "delete_service": True,
}

LEGACY_BUTTON_ATTR_TO_KEY: dict[str, str] = {
    "btn_zaman": "time",
    "btn_hajm": "volume",
    "btn_tamdid": "renew",
    "btn_change_sub": "change_subscription",
    "btn_other_links": "other_links",
    "btn_change_link": "change_link",
    "btn_copy_link": "copy_link",
    "btn_qr": "qr",
    "btn_transfer": "transfer",
    "btn_clients": "clients",
    "btn_usage_chart": "usage_chart",
    "btn_info": "info",
    "btn_del_service": "delete_service",
}

BUTTON_KEY_TO_LEGACY_ATTR = {v: k for k, v in LEGACY_BUTTON_ATTR_TO_KEY.items()}

DEFAULT_SUBSCRIPTION_SETTINGS: dict[str, Any] = {
    "default_group_ids": [],
    "user_limit": None,
    "display_mode": "classic",
    "node_prefixes": [],
    "show_prefixes_in_locations": True,
    "link_mode": "both",
    "single_config_link_indexes": "",
    "admin_login_path": "",
}

DEFAULT_TEST_SETTINGS: dict[str, Any] = {
    "volume_gb": 2.0,
    "duration_days": 3,
}

DEFAULT_RENEWAL_SETTINGS: dict[str, bool] = {
    "webhook_notifications_enabled": False,
    "renew_volume_remaining_mode": False,
}


FEATURE_SERVICE_UPGRADE = "service_upgrade"
FEATURE_SALES = "sales"
FEATURE_RESELLER_BUTTONS = "reseller_buttons"
FEATURE_CUSTOM_BUY = "custom_buy"
FEATURE_RESELLER_CAPACITY = "reseller_user_capacity"

DEFAULT_FEATURE_SALES: dict[str, bool] = {
    "shop_enabled": True,
    "reseller_enabled": True,
}

DEFAULT_CUSTOM_BUY: dict[str, Any] = {
    "enabled": False,
    "price_per_gb": 0,
    "price_per_day": 0,
    "min_gb": 1,
    "max_gb": 1000,
    "min_days": 1,
    "max_days": 365,
    "ip_limit": 0,
}

DEFAULT_RESELLER_BUTTON_SETTINGS: dict[str, bool] = {
    "credentials": True,
    "change_password": True,
    "toggle_status": True,
    "usage_report": True,
    "usage_cap": True,
    "buy_user_capacity": True,
    "delete": True,
}

DEFAULT_RESELLER_CAPACITY: dict[str, Any] = {
    "enabled": False,
    "price_per_user": 2000,
}

JSON_SETTING_COLUMNS = (
    "button_settings",
    "subscription_settings",
    "test_settings",
    "renewal_settings",
    "feature_settings",
)

LEGACY_FIELD_TO_JSON: dict[str, tuple[str, str]] = {
    **{attr: ("button_settings", key) for attr, key in LEGACY_BUTTON_ATTR_TO_KEY.items()},
    "default_group_ids": ("subscription_settings", "default_group_ids"),
    "user_limit": ("subscription_settings", "user_limit"),
    "display_mode": ("subscription_settings", "display_mode"),
    "node_prefixes": ("subscription_settings", "node_prefixes"),
    "show_prefixes_in_locations": ("subscription_settings", "show_prefixes_in_locations"),
    "subscription_link_mode": ("subscription_settings", "link_mode"),
    "single_config_link_indexes": ("subscription_settings", "single_config_link_indexes"),
    "admin_login_path": ("subscription_settings", "admin_login_path"),
    "test_volume_gb": ("test_settings", "volume_gb"),
    "test_duration_days": ("test_settings", "duration_days"),
    "webhook_notifications_enabled": ("renewal_settings", "webhook_notifications_enabled"),
    "renew_volume_remaining_mode": ("renewal_settings", "renew_volume_remaining_mode"),
}


def _merged_settings(raw: Any, defaults: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return dict(defaults)
    return {**defaults, **raw}


def button_settings(panel) -> dict[str, bool]:
    return _merged_settings(getattr(panel, "button_settings", None), DEFAULT_BUTTON_SETTINGS)


def subscription_settings(panel) -> dict[str, Any]:
    return _merged_settings(getattr(panel, "subscription_settings", None), DEFAULT_SUBSCRIPTION_SETTINGS)


def test_settings(panel) -> dict[str, Any]:
    return _merged_settings(getattr(panel, "test_settings", None), DEFAULT_TEST_SETTINGS)


def renewal_settings(panel) -> dict[str, Any]:
    return _merged_settings(getattr(panel, "renewal_settings", None), DEFAULT_RENEWAL_SETTINGS)


def feature_settings(panel) -> dict[str, Any]:
    raw = getattr(panel, "feature_settings", None)
    if isinstance(raw, dict):
        return dict(raw)
    return {}


def panel_service_upgrade(panel) -> dict[str, Any]:
    namespace = feature_settings(panel).get(FEATURE_SERVICE_UPGRADE)
    return namespace if isinstance(namespace, dict) else {}


def panel_sales_settings(panel) -> dict[str, bool]:
    raw = feature_settings(panel).get(FEATURE_SALES)
    if not isinstance(raw, dict):
        return dict(DEFAULT_FEATURE_SALES)
    return {
        **DEFAULT_FEATURE_SALES,
        **{key: bool(value) for key, value in raw.items() if key in DEFAULT_FEATURE_SALES},
    }


def panel_shop_sale_flag(panel) -> bool:
    return panel_sales_settings(panel)["shop_enabled"]


def panel_reseller_sale_flag(panel) -> bool:
    return panel_sales_settings(panel)["reseller_enabled"]


def panel_shop_sale_enabled(panel) -> bool:
    return bool(panel and panel.enable and panel_shop_sale_flag(panel))


def panel_reseller_sale_enabled(panel) -> bool:
    return bool(panel and panel.enable and panel_reseller_sale_flag(panel))


def panel_reseller_button_settings(panel) -> dict[str, bool]:
    raw = feature_settings(panel).get(FEATURE_RESELLER_BUTTONS)
    if not isinstance(raw, dict):
        return dict(DEFAULT_RESELLER_BUTTON_SETTINGS)
    return {
        **DEFAULT_RESELLER_BUTTON_SETTINGS,
        **{key: bool(value) for key, value in raw.items() if key in DEFAULT_RESELLER_BUTTON_SETTINGS},
    }


def _as_non_negative_int(value: Any, default: int = 0) -> int:
    try:
        number = int(value)
    except TypeError, ValueError:
        return default
    return number if number >= 0 else default


def _as_positive_number(value: Any, default: float) -> float:
    try:
        number = float(value)
    except TypeError, ValueError:
        return default
    return number if number > 0 else default


def _normalize_custom_buy_settings(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return dict(DEFAULT_CUSTOM_BUY)
    return {
        "enabled": bool(raw.get("enabled", DEFAULT_CUSTOM_BUY["enabled"])),
        "price_per_gb": _as_non_negative_int(raw.get("price_per_gb"), DEFAULT_CUSTOM_BUY["price_per_gb"]),
        "price_per_day": _as_non_negative_int(raw.get("price_per_day"), DEFAULT_CUSTOM_BUY["price_per_day"]),
        "min_gb": _as_positive_number(raw.get("min_gb"), DEFAULT_CUSTOM_BUY["min_gb"]),
        "max_gb": _as_positive_number(raw.get("max_gb"), DEFAULT_CUSTOM_BUY["max_gb"]),
        "min_days": max(1, _as_non_negative_int(raw.get("min_days"), DEFAULT_CUSTOM_BUY["min_days"])),
        "max_days": max(1, _as_non_negative_int(raw.get("max_days"), DEFAULT_CUSTOM_BUY["max_days"])),
        "ip_limit": _as_non_negative_int(raw.get("ip_limit"), DEFAULT_CUSTOM_BUY["ip_limit"]),
    }


def panel_custom_buy_settings(panel) -> dict[str, Any]:
    return _normalize_custom_buy_settings(feature_settings(panel).get(FEATURE_CUSTOM_BUY))


def panel_custom_buy_settings_from_feature(settings: dict[str, Any]) -> dict[str, Any]:
    raw = settings.get(FEATURE_CUSTOM_BUY) if isinstance(settings, dict) else None
    return _normalize_custom_buy_settings(raw)


def is_custom_buy_ready(settings: dict[str, Any]) -> bool:
    return bool(
        settings.get("enabled")
        and int(settings.get("price_per_gb") or 0) > 0
        and int(settings.get("price_per_day") or 0) > 0
        and float(settings.get("min_gb") or 0) > 0
        and float(settings.get("max_gb") or 0) >= float(settings.get("min_gb") or 0)
        and int(settings.get("min_days") or 0) > 0
        and int(settings.get("max_days") or 0) >= int(settings.get("min_days") or 0)
    )


def panel_custom_buy_enabled(panel) -> bool:
    return is_custom_buy_ready(panel_custom_buy_settings(panel))


def calculate_custom_buy_price(*, price_per_gb: int, price_per_day: int, storage_gb: float, duration_days: int) -> int:
    return round(float(storage_gb) * int(price_per_gb) + int(duration_days) * int(price_per_day))


def calculate_custom_buy_price_from_settings(settings: dict[str, Any], *, storage_gb: float, duration_days: int) -> int:
    return calculate_custom_buy_price(
        price_per_gb=int(settings["price_per_gb"]),
        price_per_day=int(settings["price_per_day"]),
        storage_gb=storage_gb,
        duration_days=duration_days,
    )


def calculate_panel_custom_buy_price(panel, *, storage_gb: float, duration_days: int) -> int:
    return calculate_custom_buy_price_from_settings(
        panel_custom_buy_settings(panel),
        storage_gb=storage_gb,
        duration_days=duration_days,
    )


def _compact_custom_buy_namespace(namespace: dict[str, Any]) -> dict[str, Any] | None:
    compact: dict[str, Any] = {}
    enabled = bool(namespace.get("enabled", False))
    if enabled != DEFAULT_CUSTOM_BUY["enabled"]:
        compact["enabled"] = enabled
    for key in ("price_per_gb", "price_per_day", "min_days", "max_days", "ip_limit"):
        value = _as_non_negative_int(namespace.get(key), DEFAULT_CUSTOM_BUY[key])
        if value != DEFAULT_CUSTOM_BUY[key]:
            compact[key] = value
    for key in ("min_gb", "max_gb"):
        value = _as_positive_number(namespace.get(key), DEFAULT_CUSTOM_BUY[key])
        default = DEFAULT_CUSTOM_BUY[key]
        stored = int(value) if value == int(value) else value
        if stored != default:
            compact[key] = stored
    return compact or None


def update_custom_buy_in_feature_settings(feature: dict[str, Any], **updates: Any) -> dict[str, Any]:
    current = panel_custom_buy_settings_from_feature(feature)
    for key, value in updates.items():
        if key in DEFAULT_CUSTOM_BUY:
            current[key] = value
    if current["max_gb"] < current["min_gb"]:
        current["max_gb"] = current["min_gb"]
    if current["max_days"] < current["min_days"]:
        current["max_days"] = current["min_days"]
    compact = _compact_custom_buy_namespace(current)
    if compact:
        feature[FEATURE_CUSTOM_BUY] = compact
    else:
        feature.pop(FEATURE_CUSTOM_BUY, None)
    return current


def toggle_custom_buy_enabled(feature: dict[str, Any]) -> dict[str, Any]:
    current = panel_custom_buy_settings_from_feature(feature)
    return update_custom_buy_in_feature_settings(feature, enabled=not current["enabled"])


def _normalize_reseller_capacity_settings(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return dict(DEFAULT_RESELLER_CAPACITY)
    return {
        "enabled": bool(raw.get("enabled", DEFAULT_RESELLER_CAPACITY["enabled"])),
        "price_per_user": _as_non_negative_int(raw.get("price_per_user"), DEFAULT_RESELLER_CAPACITY["price_per_user"]),
    }


def panel_reseller_capacity_settings(panel) -> dict[str, Any]:
    return _normalize_reseller_capacity_settings(feature_settings(panel).get(FEATURE_RESELLER_CAPACITY))


def panel_reseller_capacity_settings_from_feature(settings: dict[str, Any]) -> dict[str, Any]:
    raw = settings.get(FEATURE_RESELLER_CAPACITY) if isinstance(settings, dict) else None
    return _normalize_reseller_capacity_settings(raw)


def is_reseller_capacity_ready(settings: dict[str, Any]) -> bool:
    return bool(settings.get("enabled") and int(settings.get("price_per_user") or 0) > 0)


def panel_reseller_capacity_enabled(panel) -> bool:
    return is_reseller_capacity_ready(panel_reseller_capacity_settings(panel))


def _compact_reseller_capacity_namespace(namespace: dict[str, Any]) -> dict[str, Any] | None:
    compact: dict[str, Any] = {}
    enabled = bool(namespace.get("enabled", False))
    if enabled != DEFAULT_RESELLER_CAPACITY["enabled"]:
        compact["enabled"] = enabled
    price_per_user = _as_non_negative_int(namespace.get("price_per_user"), DEFAULT_RESELLER_CAPACITY["price_per_user"])
    if price_per_user != DEFAULT_RESELLER_CAPACITY["price_per_user"]:
        compact["price_per_user"] = price_per_user
    return compact or None


def update_reseller_capacity_in_feature_settings(feature: dict[str, Any], **updates: Any) -> dict[str, Any]:
    current = panel_reseller_capacity_settings_from_feature(feature)
    for key, value in updates.items():
        if key in DEFAULT_RESELLER_CAPACITY:
            current[key] = value
    compact = _compact_reseller_capacity_namespace(current)
    if compact:
        feature[FEATURE_RESELLER_CAPACITY] = compact
    else:
        feature.pop(FEATURE_RESELLER_CAPACITY, None)
    return current


def toggle_reseller_capacity_enabled(feature: dict[str, Any]) -> dict[str, Any]:
    current = panel_reseller_capacity_settings_from_feature(feature)
    return update_reseller_capacity_in_feature_settings(feature, enabled=not current["enabled"])


def panel_reseller_button_enabled(panel, key: str) -> bool:
    return bool(panel_reseller_button_settings(panel).get(key, True))


def toggle_panel_reseller_button_setting(settings: dict[str, Any], key: str) -> None:
    buttons = panel_reseller_button_settings_from_feature(settings)
    if key not in buttons:
        return
    buttons[key] = not buttons[key]
    settings[FEATURE_RESELLER_BUTTONS] = buttons


def panel_reseller_button_settings_from_feature(settings: dict[str, Any]) -> dict[str, bool]:
    raw = settings.get(FEATURE_RESELLER_BUTTONS)
    if not isinstance(raw, dict):
        return dict(DEFAULT_RESELLER_BUTTON_SETTINGS)
    return {
        **DEFAULT_RESELLER_BUTTON_SETTINGS,
        **{flag: bool(raw.get(flag, default)) for flag, default in DEFAULT_RESELLER_BUTTON_SETTINGS.items()},
    }


def toggle_panel_sales_setting(settings: dict[str, Any], key: str) -> None:
    sales = panel_sales_settings_from_feature(settings)
    sales[key] = not sales[key]
    settings[FEATURE_SALES] = sales


def panel_sales_settings_from_feature(settings: dict[str, Any]) -> dict[str, bool]:
    raw = settings.get(FEATURE_SALES)
    if not isinstance(raw, dict):
        return dict(DEFAULT_FEATURE_SALES)
    return {
        **DEFAULT_FEATURE_SALES,
        **{flag: bool(raw.get(flag, default)) for flag, default in DEFAULT_FEATURE_SALES.items()},
    }


def _compact_volume_plan(plan: dict[str, Any]) -> dict[str, Any]:
    stored: dict[str, Any] = {
        "id": plan["id"],
        "storage_gb": plan["storage_gb"],
        "price": plan["price"],
    }
    display_text = plan.get("display_button_text")
    if display_text:
        stored["display_button_text"] = display_text
    if "button_style" in plan:
        stored["button_style"] = plan.get("button_style")
    button_icon = plan.get("button_icon")
    if button_icon:
        stored["button_icon"] = button_icon
    return stored


def _compact_time_plan(plan: dict[str, Any]) -> dict[str, Any]:
    stored: dict[str, Any] = {
        "id": plan["id"],
        "duration_days": plan["duration_days"],
        "price": plan["price"],
    }
    display_text = plan.get("display_button_text")
    if display_text:
        stored["display_button_text"] = display_text
    if "button_style" in plan:
        stored["button_style"] = plan.get("button_style")
    button_icon = plan.get("button_icon")
    if button_icon:
        stored["button_icon"] = button_icon
    return stored


def _compact_service_upgrade_namespace(namespace: dict[str, Any]) -> dict[str, Any] | None:
    compact: dict[str, Any] = {}
    volume_plans = [
        _compact_volume_plan(plan)
        for plan in (_normalize_volume_upgrade_plan(item) for item in namespace.get("volume_plans") or [])
        if plan
    ]
    if volume_plans:
        compact["volume_plans"] = sorted(volume_plans, key=lambda item: float(item["storage_gb"]))
    time_plans = [
        _compact_time_plan(plan)
        for plan in (_normalize_time_upgrade_plan(item) for item in namespace.get("time_plans") or [])
        if plan
    ]
    if time_plans:
        compact["time_plans"] = sorted(time_plans, key=lambda item: int(item["duration_days"]))
    return compact or None


def compact_feature_settings(settings: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(settings, dict):
        return {}
    compact: dict[str, Any] = {}
    for key, value in settings.items():
        if key == FEATURE_SERVICE_UPGRADE and isinstance(value, dict):
            service_upgrade = _compact_service_upgrade_namespace(value)
            if service_upgrade:
                compact[key] = service_upgrade
        elif key == FEATURE_SALES and isinstance(value, dict):
            sales = {flag: bool(value[flag]) for flag in DEFAULT_FEATURE_SALES if flag in value}
            if sales != DEFAULT_FEATURE_SALES:
                compact[key] = sales
        elif key == FEATURE_RESELLER_BUTTONS and isinstance(value, dict):
            buttons = {flag: bool(value[flag]) for flag in DEFAULT_RESELLER_BUTTON_SETTINGS if flag in value}
            if buttons != DEFAULT_RESELLER_BUTTON_SETTINGS:
                compact[key] = buttons
        elif key == FEATURE_CUSTOM_BUY and isinstance(value, dict):
            custom_buy = _compact_custom_buy_namespace(value)
            if custom_buy:
                compact[key] = custom_buy
        elif key == FEATURE_RESELLER_CAPACITY and isinstance(value, dict):
            reseller_capacity = _compact_reseller_capacity_namespace(value)
            if reseller_capacity:
                compact[key] = reseller_capacity
        elif value not in (None, {}, []):
            compact[key] = value
    return compact


def _normalize_volume_upgrade_plan(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    try:
        plan_id = int(raw.get("id") or 0)
        storage_gb = float(raw.get("storage_gb") or 0)
        price = int(raw.get("price") or 0)
    except TypeError, ValueError:
        return None
    if plan_id <= 0 or storage_gb <= 0 or price < 0:
        return None
    storage_value = int(storage_gb) if storage_gb == int(storage_gb) else storage_gb
    plan: dict[str, Any] = {
        "id": plan_id,
        "storage_gb": storage_value,
        "price": price,
    }
    display_text = raw.get("display_button_text")
    if display_text:
        plan["display_button_text"] = display_text
    if "button_style" in raw:
        plan["button_style"] = raw.get("button_style")
    button_icon = raw.get("button_icon")
    if button_icon:
        plan["button_icon"] = button_icon
    return plan


def _normalize_time_upgrade_plan(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    try:
        plan_id = int(raw.get("id") or 0)
        duration_days = int(raw.get("duration_days") or 0)
        price = int(raw.get("price") or 0)
    except TypeError, ValueError:
        return None
    if plan_id <= 0 or duration_days <= 0 or price < 0:
        return None
    plan: dict[str, Any] = {
        "id": plan_id,
        "duration_days": duration_days,
        "price": price,
    }
    display_text = raw.get("display_button_text")
    if display_text:
        plan["display_button_text"] = display_text
    if "button_style" in raw:
        plan["button_style"] = raw.get("button_style")
    button_icon = raw.get("button_icon")
    if button_icon:
        plan["button_icon"] = button_icon
    return plan


def panel_volume_plans(panel) -> list[dict[str, Any]]:
    raw_plans = panel_service_upgrade(panel).get("volume_plans") or []
    plans = [_normalize_volume_upgrade_plan(item) for item in raw_plans]
    valid = [plan for plan in plans if plan]
    return sorted(valid, key=lambda item: float(item["storage_gb"]))


def panel_time_plans(panel) -> list[dict[str, Any]]:
    raw_plans = panel_service_upgrade(panel).get("time_plans") or []
    plans = [_normalize_time_upgrade_plan(item) for item in raw_plans]
    valid = [plan for plan in plans if plan]
    return sorted(valid, key=lambda item: int(item["duration_days"]))


def panel_has_volume_plans(panel) -> bool:
    return bool(panel_volume_plans(panel))


def panel_has_time_plans(panel) -> bool:
    return bool(panel_time_plans(panel))


def get_panel_volume_plan(panel, plan_id: int) -> dict[str, Any] | None:
    target_id = int(plan_id)
    for plan in panel_volume_plans(panel):
        if int(plan.get("id", 0)) == target_id:
            return plan
    return None


def get_panel_time_plan(panel, plan_id: int) -> dict[str, Any] | None:
    target_id = int(plan_id)
    for plan in panel_time_plans(panel):
        if int(plan.get("id", 0)) == target_id:
            return plan
    return None


def next_upgrade_plan_id(plans: list[dict[str, Any]]) -> int:
    if not plans:
        return 1
    return max(int(plan["id"]) for plan in plans) + 1


def _ensure_service_upgrade_namespace(feature: dict[str, Any]) -> dict[str, Any]:
    namespace = feature.get(FEATURE_SERVICE_UPGRADE)
    if not isinstance(namespace, dict):
        namespace = {}
        feature[FEATURE_SERVICE_UPGRADE] = namespace
    return namespace


def add_volume_plan_to_feature_settings(feature: dict[str, Any], *, storage_gb: float, price: int) -> dict[str, Any]:
    namespace = _ensure_service_upgrade_namespace(feature)
    plans = [_normalize_volume_upgrade_plan(item) for item in namespace.get("volume_plans") or []]
    valid = [plan for plan in plans if plan]
    new_plan = {
        "id": next_upgrade_plan_id(valid),
        "storage_gb": int(storage_gb) if storage_gb == int(storage_gb) else storage_gb,
        "price": int(price),
    }
    valid.append(new_plan)
    namespace["volume_plans"] = [_compact_volume_plan(plan) for plan in valid]
    return new_plan


def add_time_plan_to_feature_settings(feature: dict[str, Any], *, duration_days: int, price: int) -> dict[str, Any]:
    namespace = _ensure_service_upgrade_namespace(feature)
    plans = [_normalize_time_upgrade_plan(item) for item in namespace.get("time_plans") or []]
    valid = [plan for plan in plans if plan]
    new_plan = {
        "id": next_upgrade_plan_id(valid),
        "duration_days": int(duration_days),
        "price": int(price),
    }
    valid.append(new_plan)
    namespace["time_plans"] = [_compact_time_plan(plan) for plan in valid]
    return new_plan


def update_volume_plan_in_feature_settings(
    feature: dict[str, Any],
    plan_id: int,
    *,
    storage_gb: float | None = None,
    price: int | None = None,
    display_button_text: str | None = None,
    button_style: str | None = None,
    set_button_style: bool = False,
    button_icon: str | None = None,
    clear_button_icon: bool = False,
    reset_display: bool = False,
) -> dict[str, Any] | None:
    namespace = feature.get(FEATURE_SERVICE_UPGRADE)
    if not isinstance(namespace, dict):
        return None
    target_id = int(plan_id)
    updated: dict[str, Any] | None = None
    new_plans: list[dict[str, Any]] = []
    for raw in namespace.get("volume_plans") or []:
        plan = _normalize_volume_upgrade_plan(raw)
        if not plan or int(plan.get("id", 0)) != target_id:
            if plan:
                new_plans.append(plan)
            continue
        if storage_gb is not None:
            plan["storage_gb"] = int(storage_gb) if storage_gb == int(storage_gb) else storage_gb
        if price is not None:
            plan["price"] = int(price)
        if reset_display:
            plan.pop("display_button_text", None)
            plan.pop("button_style", None)
            plan.pop("button_icon", None)
        else:
            if display_button_text is not None:
                if display_button_text:
                    plan["display_button_text"] = display_button_text
                else:
                    plan.pop("display_button_text", None)
            if set_button_style:
                plan["button_style"] = button_style
            if clear_button_icon:
                plan.pop("button_icon", None)
            elif button_icon is not None:
                plan["button_icon"] = button_icon
        updated = plan
        new_plans.append(plan)
    if updated is None:
        return None
    if new_plans:
        namespace["volume_plans"] = [_compact_volume_plan(plan) for plan in new_plans]
    else:
        namespace.pop("volume_plans", None)
    if not namespace.get("volume_plans") and not namespace.get("time_plans"):
        feature.pop(FEATURE_SERVICE_UPGRADE, None)
    return updated


def update_time_plan_in_feature_settings(
    feature: dict[str, Any],
    plan_id: int,
    *,
    duration_days: int | None = None,
    price: int | None = None,
    display_button_text: str | None = None,
    button_style: str | None = None,
    set_button_style: bool = False,
    button_icon: str | None = None,
    clear_button_icon: bool = False,
    reset_display: bool = False,
) -> dict[str, Any] | None:
    namespace = feature.get(FEATURE_SERVICE_UPGRADE)
    if not isinstance(namespace, dict):
        return None
    target_id = int(plan_id)
    updated: dict[str, Any] | None = None
    new_plans: list[dict[str, Any]] = []
    for raw in namespace.get("time_plans") or []:
        plan = _normalize_time_upgrade_plan(raw)
        if not plan or int(plan.get("id", 0)) != target_id:
            if plan:
                new_plans.append(plan)
            continue
        if duration_days is not None:
            plan["duration_days"] = int(duration_days)
        if price is not None:
            plan["price"] = int(price)
        if reset_display:
            plan.pop("display_button_text", None)
            plan.pop("button_style", None)
            plan.pop("button_icon", None)
        else:
            if display_button_text is not None:
                if display_button_text:
                    plan["display_button_text"] = display_button_text
                else:
                    plan.pop("display_button_text", None)
            if set_button_style:
                plan["button_style"] = button_style
            if clear_button_icon:
                plan.pop("button_icon", None)
            elif button_icon is not None:
                plan["button_icon"] = button_icon
        updated = plan
        new_plans.append(plan)
    if updated is None:
        return None
    if new_plans:
        namespace["time_plans"] = [_compact_time_plan(plan) for plan in new_plans]
    else:
        namespace.pop("time_plans", None)
    if not namespace.get("volume_plans") and not namespace.get("time_plans"):
        feature.pop(FEATURE_SERVICE_UPGRADE, None)
    return updated


def delete_volume_plan_from_feature_settings(feature: dict[str, Any], plan_id: int) -> bool:
    namespace = feature.get(FEATURE_SERVICE_UPGRADE)
    if not isinstance(namespace, dict):
        return False
    target_id = int(plan_id)
    before = len(namespace.get("volume_plans") or [])
    remaining = [
        _compact_volume_plan(plan)
        for plan in (_normalize_volume_upgrade_plan(item) for item in namespace.get("volume_plans") or [])
        if plan and int(plan.get("id", 0)) != target_id
    ]
    if len(remaining) < before:
        if remaining:
            namespace["volume_plans"] = remaining
        else:
            namespace.pop("volume_plans", None)
        if not namespace.get("volume_plans") and not namespace.get("time_plans"):
            feature.pop(FEATURE_SERVICE_UPGRADE, None)
        return True
    return False


def delete_time_plan_from_feature_settings(feature: dict[str, Any], plan_id: int) -> bool:
    namespace = feature.get(FEATURE_SERVICE_UPGRADE)
    if not isinstance(namespace, dict):
        return False
    target_id = int(plan_id)
    before = len(namespace.get("time_plans") or [])
    remaining = [
        _compact_time_plan(plan)
        for plan in (_normalize_time_upgrade_plan(item) for item in namespace.get("time_plans") or [])
        if plan and int(plan.get("id", 0)) != target_id
    ]
    if len(remaining) < before:
        if remaining:
            namespace["time_plans"] = remaining
        else:
            namespace.pop("time_plans", None)
        if not namespace.get("volume_plans") and not namespace.get("time_plans"):
            feature.pop(FEATURE_SERVICE_UPGRADE, None)
        return True
    return False


def panel_button_enabled(panel, legacy_attr: str) -> bool:
    key = LEGACY_BUTTON_ATTR_TO_KEY.get(legacy_attr, legacy_attr)
    return bool(button_settings(panel).get(key, True))


def panel_webhook_notifications_enabled(panel) -> bool:
    return bool(renewal_settings(panel).get("webhook_notifications_enabled", False))


def panel_renew_volume_remaining_mode(panel) -> bool:
    return bool(renewal_settings(panel).get("renew_volume_remaining_mode", False))


def panel_display_mode(panel) -> str:
    return subscription_settings(panel).get("display_mode") or "classic"


def panel_user_limit(panel) -> int | None:
    value = subscription_settings(panel).get("user_limit")
    if value is None:
        return None
    try:
        return int(value)
    except TypeError, ValueError:
        return None


def panel_admin_login_path(panel) -> str:
    return str(subscription_settings(panel).get("admin_login_path") or "").strip()


def get_panel_login_url(panel) -> str:
    base = (panel.base_url or "").rstrip("/")
    extra = panel_admin_login_path(panel)
    if not extra:
        return base
    if extra.startswith("http://") or extra.startswith("https://"):
        return extra.rstrip("/")
    return f"{base}/{extra.lstrip('/')}"


def panel_subscription_link_mode(panel) -> str:
    mode = subscription_settings(panel).get("link_mode") or "both"
    return mode if mode in {"both", "main", "tunnel"} else "both"


def panel_single_config_link_indexes(panel) -> str:
    settings = subscription_settings(panel)
    if "single_config_link_indexes" not in settings:
        return ""
    value = settings.get("single_config_link_indexes")
    if value in (None, ""):
        return ""
    return str(value)


def panel_show_prefixes_in_locations(panel) -> bool:
    return bool(subscription_settings(panel).get("show_prefixes_in_locations", True))


def panel_test_volume_gb(panel) -> float:
    return float(test_settings(panel).get("volume_gb", 2.0) or 2.0)


def panel_test_duration_days(panel) -> int:
    return int(test_settings(panel).get("duration_days", 3) or 3)


def parse_group_ids_value(raw: Any) -> list[int]:
    if raw is None:
        return []
    if isinstance(raw, list):
        result = []
        for item in raw:
            try:
                result.append(int(item))
            except TypeError, ValueError:
                continue
        return result
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return []
        try:
            data = json.loads(text)
            if isinstance(data, list):
                return parse_group_ids_value(data)
        except TypeError, ValueError, json.JSONDecodeError:
            pass
        return [int(x) for x in text.split(",") if x.strip().isdigit()]
    return []


def parse_node_prefixes_value(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    if isinstance(raw, str):
        return [part.strip() for part in raw.split(",") if part.strip()]
    return []


def panel_default_group_ids(panel) -> list[int]:
    return parse_group_ids_value(subscription_settings(panel).get("default_group_ids"))


def panel_node_prefixes(panel) -> list[str]:
    return parse_node_prefixes_value(subscription_settings(panel).get("node_prefixes"))


def panel_node_prefixes_csv(panel) -> str:
    return ",".join(panel_node_prefixes(panel))


def default_panel_json_settings(
    *,
    default_group_ids: list[int] | None = None,
    user_limit: int | None = None,
) -> dict[str, dict[str, Any]]:
    subscription = copy.deepcopy(DEFAULT_SUBSCRIPTION_SETTINGS)
    if default_group_ids is not None:
        subscription["default_group_ids"] = list(default_group_ids)
    if user_limit is not None:
        subscription["user_limit"] = user_limit
    return {
        "button_settings": copy.deepcopy(DEFAULT_BUTTON_SETTINGS),
        "subscription_settings": subscription,
        "test_settings": copy.deepcopy(DEFAULT_TEST_SETTINGS),
        "renewal_settings": copy.deepcopy(DEFAULT_RENEWAL_SETTINGS),
        "feature_settings": {},
    }


def _normalize_legacy_update_value(field: str, value: Any) -> Any:
    if field == "default_group_ids":
        return parse_group_ids_value(value)
    if field == "node_prefixes":
        return parse_node_prefixes_value(value)
    if field == "single_config_link_indexes" and value is None:
        return ""
    if field == "subscription_link_mode":
        return value
    return value


def resolve_panel_update_kwargs(panel, **kwargs) -> dict[str, Any]:
    """Map legacy panel field updates into JSON column merges."""
    direct: dict[str, Any] = {}
    json_buffers: dict[str, dict[str, Any]] = {
        "button_settings": button_settings(panel) if panel else copy.deepcopy(DEFAULT_BUTTON_SETTINGS),
        "subscription_settings": subscription_settings(panel)
        if panel
        else copy.deepcopy(DEFAULT_SUBSCRIPTION_SETTINGS),
        "test_settings": test_settings(panel) if panel else copy.deepcopy(DEFAULT_TEST_SETTINGS),
        "renewal_settings": renewal_settings(panel) if panel else copy.deepcopy(DEFAULT_RENEWAL_SETTINGS),
        "feature_settings": feature_settings(panel) if panel else {},
    }
    touched_json_columns: set[str] = set()

    for key, value in kwargs.items():
        if key in JSON_SETTING_COLUMNS:
            touched_json_columns.add(key)
            if isinstance(value, dict):
                if key == "feature_settings":
                    json_buffers[key] = copy.deepcopy(value)
                else:
                    json_buffers[key].update(value)
            else:
                direct[key] = value
            continue
        mapping = LEGACY_FIELD_TO_JSON.get(key)
        if not mapping:
            direct[key] = value
            continue
        column, json_key = mapping
        json_buffers[column][json_key] = _normalize_legacy_update_value(key, value)
        touched_json_columns.add(column)

    for column in touched_json_columns:
        if column not in direct:
            direct[column] = json_buffers[column]
    return direct
