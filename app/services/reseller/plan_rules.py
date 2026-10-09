"""The single source of truth for what each reseller plan type is and allows.

Every front end (bot, user web app, admin panel) and every service reads these rules instead of
checking ``pricing_mode`` strings on its own, so a rule changes in one place for all of them.

Plan types offered for new plans:

- ``fixed``     prepaid package: price, volume > 0 and days > 0. Renewed with the same plan.
- ``unlimited`` prepaid time: price and days > 0, volume is always unlimited. Renewed with the same plan.
- ``usage``     pay per GB used, charged from the wallet every minute. No expiry, no renewal.
- ``hourly``    pay per active hour, charged from the wallet every minute. No expiry, no renewal.

``per_gb`` / ``per_tb`` are legacy: existing plans keep working and billing, none are created.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

FIXED = "fixed"
UNLIMITED = "unlimited"
USAGE = "usage"
HOURLY = "hourly"
PER_GB = "per_gb"
PER_TB = "per_tb"

ALL_MODES = (FIXED, UNLIMITED, USAGE, HOURLY, PER_GB, PER_TB)
CREATABLE_MODES = (FIXED, UNLIMITED, USAGE, HOURLY)
PREPAID_MODES = (FIXED, UNLIMITED)
PAYG_MODES = (HOURLY, USAGE)
RENEWABLE_MODES = (FIXED, UNLIMITED)
# Plans whose price changes apply to running accounts at once (billed from the live plan).
LIVE_RATE_MODES = (HOURLY, USAGE)

# Add-on keys, also used as the per-panel reseller button toggles.
ADDON_DAYS = "extra_days"
ADDON_VOLUME = "extra_volume"
ADDON_USERS = "buy_user_capacity"

ADDON_PRICE_FIELDS = {
    ADDON_DAYS: "addon_day_price",
    ADDON_VOLUME: "addon_gb_price",
    ADDON_USERS: "addon_user_price",
}


@dataclass(frozen=True)
class PlanRule:
    mode: str
    # Price field the buyer pays: ``price`` (package) or ``unit_price`` (per GB / per hour).
    price_field: str
    volume: str  # "required" | "none" | "optional"
    duration: str  # "required" | "none" | "optional"
    renewable: bool
    addons: tuple[str, ...]
    usage_cap: bool
    needs_wallet: bool


RULES: dict[str, PlanRule] = {
    FIXED: PlanRule(
        FIXED, "price", "required", "required", True, (ADDON_DAYS, ADDON_VOLUME, ADDON_USERS), False, False
    ),
    UNLIMITED: PlanRule(UNLIMITED, "price", "none", "required", True, (ADDON_DAYS, ADDON_USERS), False, False),
    USAGE: PlanRule(USAGE, "unit_price", "optional", "none", False, (ADDON_USERS,), True, True),
    HOURLY: PlanRule(HOURLY, "unit_price", "optional", "none", False, (ADDON_USERS,), False, True),
    # Legacy: keep what they did before; only user capacity is offered as an add-on.
    PER_GB: PlanRule(PER_GB, "unit_price", "optional", "optional", False, (ADDON_USERS,), False, False),
    PER_TB: PlanRule(PER_TB, "unit_price", "optional", "optional", False, (ADDON_USERS,), False, False),
}


def rule_for(mode: str | None) -> PlanRule:
    return RULES.get(mode or FIXED, RULES[FIXED])


def is_renewable(mode: str | None) -> bool:
    return rule_for(mode).renewable


def addon_price(plan, addon: str) -> int:
    """Price of one unit of ``addon`` on ``plan``; 0 when the plan type lacks it or it is switched off."""
    if plan is None or addon not in rule_for(plan.pricing_mode).addons:
        return 0
    return max(0, int(getattr(plan, ADDON_PRICE_FIELDS[addon], 0) or 0))


def validate_plan(values: dict[str, Any], *, existing_mode: str | None = None) -> str | None:
    """Check a plan before it is saved. Returns a Persian error, or None when valid.

    ``values`` uses model field names (``data_limit`` in bytes). A plan of a legacy type may be
    edited as that type, but no new plan of a legacy type is created.
    """
    mode = values.get("pricing_mode")
    if mode not in ALL_MODES:
        return "نوع پلن معتبر نیست."
    if mode not in CREATABLE_MODES and mode != existing_mode:
        return "پلن جدید فقط از نوع ثابت، نامحدود، مصرفی یا ساعتی ساخته می‌شود."
    rule = RULES[mode]

    if float(values.get(rule.price_field) or 0) <= 0:
        return {
            FIXED: "قیمت پلن ثابت باید بیشتر از صفر باشد.",
            UNLIMITED: "قیمت پلن نامحدود باید بیشتر از صفر باشد.",
            USAGE: "قیمت هر گیگ مصرف باید بیشتر از صفر باشد.",
            HOURLY: "قیمت هر ساعت باید بیشتر از صفر باشد.",
        }.get(mode, "قیمت واحد باید بیشتر از صفر باشد.")
    if rule.volume == "required" and int(values.get("data_limit") or 0) <= 0:
        return "حجم پلن ثابت باید بیشتر از صفر باشد."
    if rule.duration == "required" and int(values.get("duration") or 0) <= 0:
        return "مدت پلن باید بیشتر از صفر روز باشد."
    if int(values.get("data_limit") or 0) < 0 or int(values.get("max_users") or 0) < 0:
        return "مقدار منفی مجاز نیست."
    for field in ADDON_PRICE_FIELDS.values():
        if float(values.get(field) or 0) < 0:
            return "قیمت افزودنی نمی‌تواند منفی باشد."
    if mode in (PER_GB, PER_TB):
        max_volume = float(values.get("max_volume") or 0)
        if max_volume and max_volume < float(values.get("min_volume") or 0):
            return "حداکثر حجم نمی‌تواند از حداقل کمتر باشد."
    return None


def normalize_plan(values: dict[str, Any]) -> dict[str, Any]:
    """Clear fields the plan type does not use, so stored plans never carry contradictions."""
    rule = rule_for(values.get("pricing_mode"))
    out = dict(values)
    if rule.volume == "none":
        out["data_limit"] = 0
    if rule.duration == "none":
        out["duration"] = 0
    if rule.price_field == "unit_price":
        out["price"] = 0
    elif rule.mode in PREPAID_MODES:
        out["unit_price"] = 0
    for addon, field in ADDON_PRICE_FIELDS.items():
        if addon not in rule.addons:
            out[field] = 0
    return out


def plan_features(plan) -> dict[str, Any]:
    """What a buyer of ``plan`` gets, for guides and plan cards in every front end."""
    rule = rule_for(plan.pricing_mode)
    return {
        "mode": rule.mode,
        "renewable": rule.renewable,
        "expires": rule.duration == "required" or int(plan.duration or 0) > 0,
        "unlimited_volume": int(plan.data_limit or 0) <= 0,
        "usage_cap": rule.usage_cap,
        "needs_wallet": rule.needs_wallet,
        "extra_day_price": addon_price(plan, ADDON_DAYS),
        "extra_gb_price": addon_price(plan, ADDON_VOLUME),
        "extra_user_price": addon_price(plan, ADDON_USERS),
    }
