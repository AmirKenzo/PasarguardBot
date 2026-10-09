"""Old plans and data (setup fees, no volume/expiry, legacy types) are shown and edited correctly."""

from __future__ import annotations

from types import SimpleNamespace

from app.telegram.admin.reseller_plans.callbacks import edit_error
from app.telegram.admin.reseller_plans.service import plan_manage_buttons, plan_values_lines
from app.telegram.shared import reseller_plan_guides as guides
from app.telegram.user.reseller.helpers import (
    build_reseller_confirm_text,
    snapshot_usage_text,
    usage_history_header,
    usage_size_text,
)

GB = 1024**3
NOW = 1_800_000_000


def _plan(mode: str = "fixed", **overrides) -> SimpleNamespace:
    values = {
        "id": 3,
        "panel_code": 1,
        "pricing_mode": mode,
        "price": 100_000,
        "unit_price": 0,
        "data_limit": 10 * GB,
        "duration": 30,
        "max_users": 0,
        "addon_day_price": 0,
        "addon_gb_price": 0,
        "addon_user_price": 0,
        "min_volume": 0,
        "max_volume": 0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _callback_data(rows) -> list[str]:
    return [button.type.data.decode() for row in rows for button in row]


def test_legacy_names_match_the_pricing_labels():
    assert guides.mode_name("per_gb") == "به‌ازای گیگ"
    assert guides.mode_name("per_tb") == "به‌ازای ترابایت"
    assert guides.admin_mode_name("per_gb") == "به‌ازای گیگ (قدیمی)"
    assert guides.admin_mode_name("fixed") == "ثابت"


def test_old_hourly_setup_fee_is_shown_not_hidden():
    old = _plan("hourly", price=50_000, unit_price=2000, duration=0, data_limit=0)
    card = guides.buyer_plan_guide(old)
    assert "هزینه راه‌اندازی (پلن قدیمی): 50,000 تومان" in card
    assert "پرداخت اولیه ندارد" not in card
    confirm = build_reseller_confirm_text(old, username="u", volume=None, amount=50_000)
    assert "هزینه راه‌اندازی (پلن قدیمی)" in confirm
    assert "پرداخت اولیه:** ندارد" not in confirm
    assert any("هزینه راه‌اندازی" in line for line in plan_values_lines(old))
    new = _plan("hourly", price=0, unit_price=2000, duration=0, data_limit=0)
    assert "پرداخت اولیه ندارد" in guides.buyer_plan_guide(new)


def test_setup_fee_is_editable_only_while_it_exists():
    old = _plan("usage", price=50_000, unit_price=3000, duration=0, data_limit=0)
    assert "ResellerPlanEditField_3:price" in _callback_data(plan_manage_buttons(old))
    assert guides.parse_plan_field("price", "usage", "0") == (0, None)  # 0 removes it
    new = _plan("usage", price=0, unit_price=3000, duration=0, data_limit=0)
    assert "ResellerPlanEditField_3:price" not in _callback_data(plan_manage_buttons(new))


def test_fixed_plan_without_volume_or_days_is_not_described_as_limited():
    old = _plan(data_limit=0, duration=0)
    card = guides.buyer_plan_guide(old)
    assert "📦 حجم: نامحدود" in card
    assert "0 بایت" not in card
    assert "منقضی" not in card
    assert "تاریخ انقضا ندارد" in card


def test_renewal_without_volume_keeps_a_finite_limit():
    account = SimpleNamespace(expiration_time=NOW + 86400, max_users=0, extra_users=0)
    lines = guides.renew_preview_lines(
        account, _plan("unlimited", data_limit=0), current_limit=20 * GB, used_traffic=0, now=NOW
    )
    assert lines[0] == "📦 حجم: 20 گیگابایت (بدون تغییر)"


def test_hourly_report_shows_active_time():
    rows = [
        SimpleNamespace(billed_minutes=65, used_traffic=0, billed_amount=1000),
        SimpleNamespace(billed_minutes=None, used_traffic=3 * GB, billed_amount=500),
        SimpleNamespace(billed_minutes=None, used_traffic=1 * GB, billed_amount=0),
    ]
    assert snapshot_usage_text(rows, 0) == "1 ساعت و 5 دقیقه"
    assert snapshot_usage_text(rows, 1) == "2 گیگابایت"
    assert guides.format_active_minutes(0) == "0 دقیقه"
    assert guides.format_active_minutes(120) == "2 ساعت"
    title, column = usage_history_header(SimpleNamespace(pricing_mode="hourly", username="a"))
    assert "گزارش کسر" in title
    assert column == "زمان فعال"
    assert "گزارش مصرف" in usage_history_header(SimpleNamespace(pricing_mode="usage", username="a"))[0]


def test_legacy_plan_broken_in_two_fields_can_be_fixed_in_any_order():
    legacy = _plan(data_limit=0, duration=0)
    assert edit_error(legacy, "data_limit", 10 * GB) is None
    assert edit_error(legacy, "duration", 30) is None
    assert edit_error(legacy, "price", 50_000) is None
    # The edited field itself must still follow the rules.
    assert edit_error(legacy, "price", 0)
    assert edit_error(_plan(), "data_limit", 0)


def test_usage_report_uses_adaptive_units():
    mb = 1024 * 1024
    rows = [
        SimpleNamespace(billed_minutes=None, used_traffic=GB + 250 * mb, billed_amount=732),
        SimpleNamespace(billed_minutes=None, used_traffic=GB, billed_amount=0),
    ]
    assert snapshot_usage_text(rows, 0) == "250 مگابایت"
    assert usage_size_text(0) == "0 بایت"
    assert usage_size_text(512) == "512 بایت"
    assert usage_size_text(10 * mb) == "10 مگابایت"
    assert usage_size_text(int(1.25 * GB)) == "1.25 گیگابایت"
    assert usage_size_text(int(12.5 * GB)) == "12.5 گیگابایت"
    assert usage_size_text(1500 * GB) == "1,500 گیگابایت"
