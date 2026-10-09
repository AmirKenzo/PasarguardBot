"""Plan type names, guides, wizard fields and previews the bot shows for reseller plans."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.reseller.addons import ADDON_MAX_QUANTITY, AddonQuote
from app.services.reseller.plan_rules import ADDON_DAYS, ADDON_USERS, ADDON_VOLUME, CREATABLE_MODES
from app.telegram.shared import reseller_plan_guides as guides

GB = 1024**3
NOW = 1_800_000_000


def _plan(mode: str = "fixed", **overrides) -> SimpleNamespace:
    values = {
        "id": 1,
        "pricing_mode": mode,
        "price": 100_000,
        "unit_price": 0,
        "data_limit": 50 * GB,
        "duration": 30,
        "max_users": 50,
        "addon_day_price": 0,
        "addon_gb_price": 0,
        "addon_user_price": 0,
        "min_volume": 0,
        "max_volume": 0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _account(**overrides) -> SimpleNamespace:
    values = {
        "username": "agency",
        "expiration_time": NOW + 10 * 86400,
        "data_limit": 50 * GB,
        "max_users": 60,
        "extra_users": 10,
        "status": "active",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_type_names_are_exact():
    assert guides.mode_name("fixed") == "ثابت"
    assert guides.mode_name("unlimited") == "نامحدود (زمانی)"
    assert guides.mode_name("usage") == "مصرفی (بر اساس حجم مصرف)"
    assert guides.mode_name("hourly") == "ساعتی (بر اساس زمان فعال بودن)"
    assert [guides.mode_short_name(m) for m in CREATABLE_MODES] == ["ثابت", "نامحدود", "مصرفی", "ساعتی"]
    assert guides.ADDON_NAMES == {ADDON_DAYS: "روز اضافه", ADDON_VOLUME: "حجم اضافه", ADDON_USERS: "یوزر اضافه"}


@pytest.mark.parametrize("mode", CREATABLE_MODES)
def test_admin_guide_has_every_section(mode: str):
    text = guides.admin_type_guide(mode, guides.GuideContext(grace_days=5, min_wallet=50_000))
    for header in ("این پلن چیست؟", "فیلدهای لازم", "خریدار چه کارهایی", "کارهای خودکار ربات", "نکته‌ها"):
        assert header in text
    assert guides.mode_name(mode) in text


def test_admin_guide_quotes_the_settings():
    prepaid = guides.admin_type_guide("fixed", guides.GuideContext(grace_days=5, min_wallet=50_000))
    assert "5 روز" in prepaid
    payg = guides.admin_type_guide("usage", guides.GuideContext(grace_days=5, min_wallet=50_000))
    assert "50,000 تومان" in payg
    assert "تعلیق" in payg


def test_creation_asks_only_the_fields_of_the_type():
    assert guides.create_fields("fixed") == (
        "price",
        "data_limit",
        "max_users",
        "duration",
        "addon_day_price",
        "addon_gb_price",
        "addon_user_price",
    )
    assert guides.create_fields("unlimited") == (
        "price",
        "max_users",
        "duration",
        "addon_day_price",
        "addon_user_price",
    )
    assert guides.create_fields("usage") == ("unit_price", "data_limit", "max_users", "addon_user_price")
    assert guides.create_fields("hourly") == ("unit_price", "data_limit", "max_users", "addon_user_price")


def test_user_addon_is_skipped_when_users_are_unlimited():
    assert guides.next_create_field("usage", "max_users", {"max_users": 0}) is None
    assert guides.next_create_field("usage", "max_users", {"max_users": 5}) == "addon_user_price"
    assert guides.next_create_field("fixed", "addon_gb_price", {"max_users": 0}) is None
    assert guides.next_create_field("fixed", None) == "price"


@pytest.mark.parametrize(
    ("field", "mode", "raw", "value", "error"),
    [
        ("price", "fixed", "120,000", 120_000, False),
        ("price", "fixed", "۱۲۰٬۰۰۰", 120_000, False),
        ("price", "fixed", "0", None, True),
        ("price", "fixed", "-5", None, True),
        ("data_limit", "fixed", "0", None, True),
        ("data_limit", "fixed", "2.5", 2.5, False),
        ("data_limit", "usage", "0", 0, False),
        ("duration", "unlimited", "0", None, True),
        ("duration", "fixed", "1.5", None, True),
        ("max_users", "fixed", "0", 0, False),
        ("addon_day_price", "fixed", "0", 0, False),
        ("addon_gb_price", "fixed", "abc", None, True),
    ],
)
def test_wizard_input_rules(field, mode, raw, value, error):
    parsed, message = guides.parse_plan_field(field, mode, raw)
    assert (message is not None) is error
    assert parsed == value


def test_prompts_name_the_unit_and_zero_meaning():
    assert "0 = خاموش" in guides.field_prompt("addon_day_price", "fixed")
    assert "0 = نامحدود" in guides.field_prompt("data_limit", "hourly")
    assert "بیشتر از صفر" in guides.field_prompt("data_limit", "fixed")
    assert "هر ساعت" in guides.field_prompt("unit_price", "hourly")
    assert "هر گیگ مصرف" in guides.field_prompt("unit_price", "usage")


def test_review_summary_has_no_upfront_payment_for_payg():
    summary = guides.plan_values_summary(
        {"pricing_mode": "hourly", "unit_price": 2000, "data_limit": 0, "max_users": 0}
    )
    assert "پرداخت اولیه: ندارد" in summary
    assert "سقف کل ترافیک: نامحدود" in summary


def test_buyer_guide_lists_addons_with_prices_and_off_ones_as_dash():
    plan = _plan("fixed", addon_day_price=2000, addon_gb_price=0, addon_user_price=3000)
    includes = "\n".join(guides.plan_includes_lines(plan))
    assert "✓ روز اضافه — هر روز 2,000 تومان" in includes
    assert "– حجم اضافه" in includes
    assert "✓ یوزر اضافه — هر یوزر 3,000 تومان" in includes
    assert "✓ تمدید با همین پلن" in includes

    how = "\n".join(guides.plan_how_it_works_lines(plan, guides.GuideContext(grace_days=7)))
    assert "حجم اضافه" not in how  # off add-ons are not mentioned
    assert "روز اضافه" in how
    assert "7 روز" in how
    assert "چیزی ریست نمی‌شود" in how


def test_buyer_guide_for_unlimited_and_usage():
    unlimited = guides.buyer_plan_guide(_plan("unlimited", data_limit=0))
    assert "📦 حجم: نامحدود" in unlimited
    assert "حجم اضافه" not in unlimited
    usage = guides.buyer_plan_guide(
        _plan("usage", price=0, unit_price=5000, duration=0, data_limit=0, max_users=0),
        guides.GuideContext(min_wallet=100_000),
    )
    assert "این پلن چطور کار می‌کند؟" in usage
    assert "پرداخت اولیه ندارد" in usage
    assert "100,000 تومان" in usage
    assert "بدون انقضا" in usage
    assert "یوزر اضافه" not in usage  # unlimited users: nothing to extend


def test_max_users_label():
    assert guides.max_users_label(60, 10) == "50 پلن + 10 اضافه"
    assert guides.max_users_label(50, 0) == "50"
    assert guides.max_users_label(0, 3) == "نامحدود"


def test_renew_preview_adds_volume_and_days_without_reset():
    lines = guides.renew_preview_lines(_account(), _plan(), current_limit=40 * GB, used_traffic=10 * GB, now=NOW)
    text = "\n".join(lines)
    assert "40 گیگابایت ← 90 گیگابایت" in text
    assert "+30 روز" in text
    assert "50 پلن + 10 اضافه (بدون تغییر)" in text


def test_renew_preview_for_expired_and_unlimited():
    expired = _account(expiration_time=NOW - 86400)
    text = "\n".join(
        guides.renew_preview_lines(expired, _plan("unlimited", data_limit=0), current_limit=0, used_traffic=0, now=NOW)
    )
    assert "نامحدود (بدون تغییر)" in text
    assert "از امروز" in text
    # An unlimited panel limit starts from what is already used.
    text = "\n".join(guides.renew_preview_lines(_account(), _plan(), current_limit=0, used_traffic=5 * GB, now=NOW))
    assert "نامحدود ← 55 گیگابایت" in text


def test_addon_previews():
    users = AddonQuote(ADDON_USERS, 10, 3000, 30000, 50, 60)
    assert guides.addon_preview_lines(users) == ["👥 سقف یوزر: 50 ← 60 (+10 یوزر، دائمی)"]
    volume = AddonQuote(ADDON_VOLUME, 10, 1000, 10000, 10 * GB, 20 * GB)
    assert "10 گیگابایت ← 20 گیگابایت" in guides.addon_preview_lines(volume)[0]
    days = AddonQuote(ADDON_DAYS, 5, 1000, 5000, NOW, NOW + 5 * 86400)
    assert "از امروز" in guides.addon_preview_lines(days, expired=True)[0]


def test_addon_quantity_parsing():
    assert guides.parse_addon_quantity(ADDON_DAYS, "15") == (15, None)
    assert guides.parse_addon_quantity(ADDON_USERS, "0")[1]
    assert guides.parse_addon_quantity(ADDON_VOLUME, "2.5")[1]
    too_many = str(ADDON_MAX_QUANTITY[ADDON_DAYS] + 1)
    assert guides.parse_addon_quantity(ADDON_DAYS, too_many)[1]


def test_addon_tokens_round_trip():
    for token, addon in guides.ADDON_TOKENS.items():
        assert guides.ADDON_TOKEN_OF[addon] == token
