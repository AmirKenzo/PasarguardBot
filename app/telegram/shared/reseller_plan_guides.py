"""Reseller plan type names, guides and input checks shared by the admin and user bot flows.

Everything here is pure (no Telegram, no DB) except ``load_guide_context``, so the texts can be
unit tested and both sides of the bot explain the plan types with the same words.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.reseller.addons import ADDON_MAX_QUANTITY
from app.services.reseller.plan_rules import (
    ADDON_DAYS,
    ADDON_PRICE_FIELDS,
    ADDON_USERS,
    ADDON_VOLUME,
    CREATABLE_MODES,
    FIXED,
    HOURLY,
    PER_GB,
    PER_TB,
    UNLIMITED,
    USAGE,
    addon_price,
    plan_features,
    rule_for,
)
from app.utils.formatting.traffic import format_size

MODE_NAMES: dict[str, str] = {
    FIXED: "ثابت",
    UNLIMITED: "نامحدود (زمانی)",
    USAGE: "مصرفی (بر اساس حجم مصرف)",
    HOURLY: "ساعتی (بر اساس زمان فعال بودن)",
    PER_GB: "به‌ازای گیگ",
    PER_TB: "به‌ازای ترابایت",
}
MODE_SHORT_NAMES: dict[str, str] = {
    FIXED: "ثابت",
    UNLIMITED: "نامحدود",
    USAGE: "مصرفی",
    HOURLY: "ساعتی",
    PER_GB: "گیگ",
    PER_TB: "ترا",
}
MODE_ICONS: dict[str, str] = {FIXED: "📦", UNLIMITED: "♾", USAGE: "📊", HOURLY: "⏱"}

ADDON_NAMES: dict[str, str] = {ADDON_DAYS: "روز اضافه", ADDON_VOLUME: "حجم اضافه", ADDON_USERS: "یوزر اضافه"}
ADDON_UNITS: dict[str, str] = {ADDON_DAYS: "روز", ADDON_VOLUME: "گیگ", ADDON_USERS: "یوزر"}
# Short tokens keep inline callback data well under Telegram's 64-byte limit.
ADDON_TOKENS: dict[str, str] = {"d": ADDON_DAYS, "v": ADDON_VOLUME, "u": ADDON_USERS}
ADDON_TOKEN_OF: dict[str, str] = {addon: token for token, addon in ADDON_TOKENS.items()}
ADDON_PRESETS: dict[str, tuple[int, ...]] = {
    ADDON_DAYS: (7, 15, 30, 60, 90, 180),
    ADDON_VOLUME: (10, 25, 50, 100, 200, 500),
    ADDON_USERS: (5, 10, 20, 30, 50, 100),
}

DEFAULT_GRACE_DAYS = 7


def mode_name(mode: str | None) -> str:
    return MODE_NAMES.get(mode or "", mode or "—")


def mode_short_name(mode: str | None) -> str:
    return MODE_SHORT_NAMES.get(mode or "", mode or "—")


LEGACY_SUFFIX = " (قدیمی)"


def _is_legacy(mode: str | None) -> bool:
    return mode in MODE_NAMES and mode not in CREATABLE_MODES


def admin_mode_name(mode: str | None) -> str:
    """Type name for admin screens: legacy types are marked so admins know no new ones are made."""
    return mode_name(mode) + (LEGACY_SUFFIX if _is_legacy(mode) else "")


def admin_mode_short_name(mode: str | None) -> str:
    return mode_short_name(mode) + (LEGACY_SUFFIX if _is_legacy(mode) else "")


def setup_fee(plan) -> int:
    """Upfront charge of a usage/hourly plan; only old plans still carry one (new ones are 0)."""
    from app.services.billing.reseller_pricing import calculate_purchase_price

    if plan is None or plan.pricing_mode not in (USAGE, HOURLY):
        return 0
    return max(0, int(calculate_purchase_price(plan) or 0))


SETUP_FEE_LABEL = "هزینه راه‌اندازی (پلن قدیمی)"


def toman(value: float | int | None) -> str:
    return f"{int(value or 0):,} تومان"


@dataclass(frozen=True)
class GuideContext:
    """Global reseller settings the guides quote (grace days before purge, minimum wallet)."""

    grace_days: int = DEFAULT_GRACE_DAYS
    min_wallet: int = 0


async def load_guide_context() -> GuideContext:
    from app.db.crud.settings import SettingsManager

    settings = await SettingsManager().get_settings()
    if not settings:
        return GuideContext()
    grace = int(getattr(settings, "reseller_grace_days", DEFAULT_GRACE_DAYS) or DEFAULT_GRACE_DAYS)
    min_wallet = int(getattr(settings, "reseller_min_wallet_balance", 0) or 0)
    return GuideContext(grace_days=max(1, grace), min_wallet=max(0, min_wallet))


# --------------------------------------------------------------------------------------------
# Admin: plan type guides
# --------------------------------------------------------------------------------------------


def _auto_expiry_lines(ctx: GuideContext) -> list[str]:
    return [
        "• در پایان مدت، نمایندگی «منقضی» و ادمین پنل غیرفعال می‌شود و به نماینده اطلاع داده می‌شود.",
        f"• اگر نماینده تا {ctx.grace_days} روز بعد از انقضا تمدید نکند، ادمین و همه یوزرهایش از پنل حذف می‌شوند.",
    ]


def _auto_wallet_lines(ctx: GuideContext, what: str) -> list[str]:
    min_line = (
        f"• برای خرید، حداقل {toman(ctx.min_wallet)} موجودی کیف پول لازم است (از تنظیمات نمایندگی)."
        if ctx.min_wallet
        else "• حداقل موجودی برای خرید از تنظیمات نمایندگی خوانده می‌شود (الان صفر است)."
    )
    return [
        min_line,
        f"• هر دقیقه هزینه {what} محاسبه و از کیف پول نماینده کسر می‌شود.",
        "• اگر موجودی تمام شود، ادمین پنل «تعلیق» می‌شود و بعد از شارژ کیف پول، خودکار دوباره فعال می‌شود.",
    ]


def admin_type_guide(mode: str, ctx: GuideContext | None = None) -> str:
    """Full guide shown to the admin right after choosing a plan type."""
    ctx = ctx or GuideContext()
    title = f"📘 **راهنمای پلن {admin_mode_name(mode)}**"
    if mode == FIXED:
        sections = [
            (
                "▫️ **این پلن چیست؟**",
                [
                    "بسته پیش‌پرداخت: نماینده یک‌بار مبلغ پلن را می‌پردازد و حجم و مدت مشخصی می‌گیرد.",
                ],
            ),
            (
                "▫️ **فیلدهای لازم:**",
                [
                    "• قیمت پلن (تومان، بیشتر از صفر)",
                    "• حجم (گیگ، بیشتر از صفر)",
                    "• حداکثر تعداد یوزر (0 = نامحدود)",
                    "• مدت (روز، بیشتر از صفر)",
                    "• قیمت افزودنی‌ها: روز اضافه، حجم اضافه، یوزر اضافه (0 = خاموش)",
                ],
            ),
            (
                "▫️ **خریدار چه کارهایی می‌تواند بکند؟**",
                [
                    "• تمدید با همین پلن: روزهای پلن از تاریخ انقضای فعلی و حجم پلن روی حجم فعلی اضافه می‌شود؛ "
                    "روز و حجم باقی‌مانده حفظ می‌شود و چیزی ریست نمی‌شود.",
                    "• خرید روز اضافه (حتی بعد از انقضا)، حجم اضافه (قبل از انقضا) و یوزر اضافه (دائمی)؛ "
                    "فقط افزودنی‌هایی که قیمتشان را تنظیم کنید.",
                    "• استفاده از کد تخفیف هنگام خرید و تمدید.",
                ],
            ),
            ("▫️ **کارهای خودکار ربات:**", _auto_expiry_lines(ctx)),
            (
                "▫️ **نکته‌ها:**",
                [
                    "• تغییر قیمت فقط روی خریدها و تمدیدهای بعدی اثر دارد.",
                    "• پلن غیرفعال به خریدار جدید نشان داده نمی‌شود، ولی نماینده‌های فعلی همچنان آن را تمدید می‌کنند.",
                ],
            ),
        ]
    elif mode == UNLIMITED:
        sections = [
            (
                "▫️ **این پلن چیست؟**",
                [
                    "بسته پیش‌پرداخت زمانی: نماینده یک‌بار مبلغ پلن را می‌پردازد؛ حجم همیشه نامحدود است و فقط مدت دارد.",
                ],
            ),
            (
                "▫️ **فیلدهای لازم:**",
                [
                    "• قیمت پلن (تومان، بیشتر از صفر)",
                    "• حداکثر تعداد یوزر (0 = نامحدود)",
                    "• مدت (روز، بیشتر از صفر)",
                    "• قیمت افزودنی‌ها: روز اضافه، یوزر اضافه (0 = خاموش)",
                ],
            ),
            (
                "▫️ **خریدار چه کارهایی می‌تواند بکند؟**",
                [
                    "• تمدید با همین پلن: روزهای پلن از تاریخ انقضای فعلی اضافه می‌شود؛ روزهای باقی‌مانده حفظ می‌شود.",
                    "• خرید روز اضافه (حتی بعد از انقضا) و یوزر اضافه (دائمی)؛ فقط افزودنی‌هایی که قیمتشان را تنظیم کنید.",
                    "• استفاده از کد تخفیف هنگام تمدید.",
                ],
            ),
            ("▫️ **کارهای خودکار ربات:**", _auto_expiry_lines(ctx)),
            (
                "▫️ **نکته‌ها:**",
                [
                    "• حجم پرسیده نمی‌شود و همیشه نامحدود است؛ حجم اضافه هم برای این نوع وجود ندارد.",
                    "• تغییر قیمت فقط روی خریدها و تمدیدهای بعدی اثر دارد.",
                ],
            ),
        ]
    elif mode == USAGE:
        sections = [
            (
                "▫️ **این پلن چیست؟**",
                [
                    "پرداخت به‌ازای مصرف: پرداخت اولیه ندارد و به‌ازای هر گیگ مصرف‌شده از کیف پول نماینده کسر می‌شود. "
                    "انقضا و تمدید ندارد.",
                ],
            ),
            (
                "▫️ **فیلدهای لازم:**",
                [
                    "• قیمت هر گیگ مصرف (تومان، بیشتر از صفر)",
                    "• سقف کل ترافیک (گیگ، اختیاری؛ 0 = نامحدود)",
                    "• حداکثر تعداد یوزر (0 = نامحدود)",
                    "• قیمت یوزر اضافه (0 = خاموش)",
                ],
            ),
            (
                "▫️ **خریدار چه کارهایی می‌تواند بکند؟**",
                [
                    "• برای خودش سقف مصرف تعیین کند تا بیشتر از آن هزینه نشود.",
                    "• گزارش مصرف و هزینه‌ها را ببیند.",
                    "• پنل را موقتاً غیرفعال و دوباره فعال کند.",
                    "• یوزر اضافه بخرد (اگر قیمتش را تنظیم کنید).",
                ],
            ),
            (
                "▫️ **کارهای خودکار ربات:**",
                [
                    *_auto_wallet_lines(ctx, "حجم مصرف‌شده"),
                    "• با رسیدن مصرف به سقف دستی نماینده، پنل غیرفعال می‌شود.",
                ],
            ),
            (
                "▫️ **نکته‌ها:**",
                [
                    "• تغییر قیمت هر گیگ از همان لحظه روی همه نماینده‌های این پلن اعمال می‌شود و به آن‌ها اطلاع داده می‌شود.",
                    "• مدت و روز اضافه برای این نوع وجود ندارد.",
                ],
            ),
        ]
    elif mode == HOURLY:
        sections = [
            (
                "▫️ **این پلن چیست؟**",
                [
                    "پرداخت به‌ازای زمان فعال بودن: پرداخت اولیه ندارد و به‌ازای هر ساعتی که پنل فعال است "
                    "(دقیقه‌ای) از کیف پول نماینده کسر می‌شود. انقضا و تمدید ندارد.",
                ],
            ),
            (
                "▫️ **فیلدهای لازم:**",
                [
                    "• قیمت هر ساعت (تومان، بیشتر از صفر)",
                    "• سقف کل ترافیک (گیگ، اختیاری؛ 0 = نامحدود)",
                    "• حداکثر تعداد یوزر (0 = نامحدود)",
                    "• قیمت یوزر اضافه (0 = خاموش)",
                ],
            ),
            (
                "▫️ **خریدار چه کارهایی می‌تواند بکند؟**",
                [
                    "• پنل را غیرفعال کند تا در این مدت هزینه‌ای کسر نشود، و هر وقت خواست دوباره فعالش کند.",
                    "• گزارش هزینه‌ها را ببیند.",
                    "• یوزر اضافه بخرد (اگر قیمتش را تنظیم کنید).",
                ],
            ),
            ("▫️ **کارهای خودکار ربات:**", _auto_wallet_lines(ctx, "زمان فعال بودن")),
            (
                "▫️ **نکته‌ها:**",
                [
                    "• تغییر قیمت هر ساعت از همان لحظه روی همه نماینده‌های این پلن اعمال می‌شود و به آن‌ها اطلاع داده می‌شود.",
                    "• هزینه راه‌اندازی یا پرداخت اولیه ندارد.",
                ],
            ),
        ]
    else:
        sections = [
            (
                "▫️ **این پلن چیست؟**",
                [
                    "نوع قدیمی: پلن‌های موجود مثل قبل کار و صورتحساب می‌کنند، ولی پلن جدیدی از این نوع ساخته نمی‌شود.",
                ],
            ),
        ]
    body = ["\n".join([header, *lines]) for header, lines in sections]
    return "\n\n".join([title, *body])


def admin_guide_summary(plan) -> str:
    """One short paragraph for the admin plan detail view."""
    mode = plan.pricing_mode
    return {
        FIXED: "پیش‌پرداخت؛ حجم و مدت مشخص. تمدید فقط با همین پلن؛ انقضا ← مهلت ← حذف از پنل.",
        UNLIMITED: "پیش‌پرداخت؛ حجم نامحدود و مدت مشخص. تمدید فقط با همین پلن؛ انقضا ← مهلت ← حذف از پنل.",
        USAGE: "بدون پرداخت اولیه؛ کسر دقیقه‌ای به‌ازای هر گیگ مصرف. با تمام شدن موجودی تعلیق و بعد از شارژ فعال می‌شود.",
        HOURLY: "بدون پرداخت اولیه؛ کسر دقیقه‌ای به‌ازای زمان فعال بودن. با تمام شدن موجودی تعلیق و بعد از شارژ فعال می‌شود.",
    }.get(mode, "نوع قدیمی؛ مثل قبل کار می‌کند و پلن جدید از آن ساخته نمی‌شود.")


# --------------------------------------------------------------------------------------------
# Admin: plan creation / edit fields
# --------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class PlanField:
    """One value the admin types for a plan; ``name`` is the plan model field."""

    name: str
    allow_zero: bool
    integer: bool = True


ADDON_FIELD_HINTS: dict[str, str] = {
    "addon_day_price": "ℹ️ نماینده می‌تواند بدون تمدید کامل، چند روز به اعتبارش اضافه کند (حتی بعد از انقضا).",
    "addon_gb_price": "ℹ️ نماینده می‌تواند قبل از انقضا، بدون تمدید کامل حجم بیشتری بخرد.",
    "addon_user_price": "ℹ️ نماینده می‌تواند سقف یوزرش را به‌صورت دائمی بالا ببرد (فقط وقتی سقف یوزر نامحدود نیست).",
}
ADDON_FIELD_LABELS: dict[str, str] = {
    "addon_day_price": "قیمت هر روز اضافه",
    "addon_gb_price": "قیمت هر گیگ حجم اضافه",
    "addon_user_price": "قیمت هر یوزر اضافه",
}


def plan_field(name: str, mode: str) -> PlanField:
    rule = rule_for(mode)
    if name == "price" and mode in (USAGE, HOURLY):
        # The old setup fee: 0 removes it.
        return PlanField(name, allow_zero=True)
    if name in ("price", "unit_price"):
        return PlanField(name, allow_zero=False)
    if name == "data_limit":
        return PlanField(name, allow_zero=rule.volume != "required", integer=False)
    if name == "duration":
        return PlanField(name, allow_zero=rule.duration != "required")
    return PlanField(name, allow_zero=True)


def create_fields(mode: str) -> tuple[str, ...]:
    """Fields asked, in order, when creating a plan of ``mode``."""
    rule = rule_for(mode)
    fields: list[str] = [rule.price_field]
    if rule.volume != "none":
        fields.append("data_limit")
    fields.append("max_users")
    if rule.duration == "required":
        fields.append("duration")
    fields.extend(ADDON_PRICE_FIELDS[addon] for addon in rule.addons)
    return tuple(fields)


def editable_fields(mode: str, plan=None) -> tuple[str, ...]:
    """Fields the admin may edit on an existing plan (legacy types keep their own fields).

    A usage/hourly plan that still has an old setup fee also offers it, so it can be removed.
    """
    fields = create_fields(mode)
    if plan is not None and mode in (USAGE, HOURLY) and int(plan.price or 0) > 0:
        fields = (*fields, "price")
    return fields


def next_create_field(mode: str, current: str | None, values: dict | None = None) -> str | None:
    """The field after ``current`` (or the first one); skips the user add-on when users are unlimited."""
    fields = create_fields(mode)
    index = 0 if current is None else fields.index(current) + 1
    values = values or {}
    while index < len(fields):
        name = fields[index]
        if name == "addon_user_price" and "max_users" in values and int(values.get("max_users") or 0) <= 0:
            index += 1
            continue
        return name
    return None


def field_label(name: str, mode: str) -> str:
    if name == "price":
        return SETUP_FEE_LABEL if mode in (USAGE, HOURLY) else "قیمت پلن"
    if name == "unit_price":
        return "قیمت هر ساعت" if mode == HOURLY else "قیمت هر گیگ مصرف" if mode == USAGE else "قیمت واحد"
    if name == "data_limit":
        return "حجم پلن" if rule_for(mode).volume == "required" else "سقف کل ترافیک"
    if name == "max_users":
        return "حداکثر تعداد یوزر"
    if name == "duration":
        return "مدت پلن"
    return ADDON_FIELD_LABELS.get(name, name)


def field_prompt(name: str, mode: str) -> str:
    """The question sent for ``name``, with the unit and what 0 means."""
    label = field_label(name, mode)
    if name == "price" and mode in (USAGE, HOURLY):
        return f"💳 **{label}** را به تومان ارسال کنید (0 = حذف هزینه راه‌اندازی):"
    if name in ("price", "unit_price"):
        return f"💰 **{label}** را به تومان ارسال کنید (بیشتر از صفر):"
    if name == "data_limit":
        if rule_for(mode).volume == "required":
            return f"📦 **{label}** را به گیگ ارسال کنید (بیشتر از صفر):"
        return f"📦 **{label}** نماینده را به گیگ ارسال کنید (0 = نامحدود):"
    if name == "max_users":
        return f"👥 **{label}** نماینده را ارسال کنید (تعداد یوزرهایی که می‌تواند بسازد؛ 0 = نامحدود):"
    if name == "duration":
        return f"⏰ **{label}** را به روز ارسال کنید (بیشتر از صفر):"
    hint = ADDON_FIELD_HINTS.get(name, "")
    icon = {"addon_day_price": "📅", "addon_gb_price": "📦", "addon_user_price": "👥"}.get(name, "🧩")
    return f"{icon} **{label}** را به تومان ارسال کنید (0 = خاموش):\n{hint}"


_DIGIT_MAP = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def parse_number(raw: str | None, *, allow_zero: bool, integer: bool = True) -> tuple[float | int | None, str | None]:
    """Parse an admin/user typed number (Persian digits and separators allowed). Returns (value, error)."""
    text = (raw or "").strip().translate(_DIGIT_MAP)
    for sep in (",", "٬", "،", " "):
        text = text.replace(sep, "")
    text = text.replace("٫", ".")
    if not text:
        return None, "لطفاً یک عدد ارسال کنید."
    try:
        value: float | int = int(text) if integer else float(text)
    except ValueError:
        return None, "فقط عدد صحیح ارسال کنید." if integer else "فقط عدد ارسال کنید."
    if value != value or value in (float("inf"), float("-inf")):
        return None, "عدد معتبر ارسال کنید."
    if value < 0:
        return None, "عدد منفی مجاز نیست."
    if value == 0 and not allow_zero:
        return None, "مقدار باید بیشتر از صفر باشد."
    return value, None


def parse_plan_field(name: str, mode: str, raw: str | None) -> tuple[float | int | None, str | None]:
    field = plan_field(name, mode)
    return parse_number(raw, allow_zero=field.allow_zero, integer=field.integer)


def format_field_value(name: str, value) -> str:
    """Human value of a stored plan field (``data_limit`` in bytes)."""
    if name == "data_limit":
        return format_size(int(value or 0)) if int(value or 0) > 0 else "نامحدود"
    if name == "max_users":
        return str(int(value or 0)) if int(value or 0) > 0 else "نامحدود"
    if name == "duration":
        return f"{int(value or 0)} روز" if int(value or 0) > 0 else "بدون انقضا"
    if name in ADDON_FIELD_LABELS:
        return toman(value) if int(value or 0) > 0 else "خاموش"
    return toman(value)


def plan_values_summary(values: dict) -> str:
    """Lines for the creation review screen, from model field values (``data_limit`` in bytes)."""
    mode = values.get("pricing_mode") or FIXED
    lines = [f"**📋 نوع:** {mode_name(mode)}"]
    for name in create_fields(mode):
        lines.append(f"• {field_label(name, mode)}: {format_field_value(name, values.get(name))}")
    if mode in (USAGE, HOURLY):
        fee = int(values.get("price") or 0)
        lines.append(f"• {SETUP_FEE_LABEL}: {toman(fee)}" if fee > 0 else "• پرداخت اولیه: ندارد")
    return "\n".join(lines)


def is_creatable(mode: str | None) -> bool:
    return mode in CREATABLE_MODES


# --------------------------------------------------------------------------------------------
# Buyer: what a plan includes and how it works
# --------------------------------------------------------------------------------------------


def plan_price_line(plan) -> str:
    mode = plan.pricing_mode
    if mode in (FIXED, UNLIMITED):
        return f"{toman(plan.price)} (یک‌جا)"
    if mode == USAGE:
        return f"{toman(plan.unit_price)} به‌ازای هر گیگ مصرف"
    if mode == HOURLY:
        return f"{toman(plan.unit_price)} به‌ازای هر ساعت فعال بودن"
    if mode == PER_TB:
        return f"{toman(plan.unit_price)} به‌ازای هر ترابایت"
    return f"{toman(plan.unit_price)} به‌ازای هر گیگابایت"


def _addon_line(enabled_price: int, name: str, unit: str) -> str:
    if enabled_price > 0:
        return f"✓ {name} — هر {unit} {toman(enabled_price)}"
    return f"– {name}"


def plan_includes_lines(plan) -> list[str]:
    """What the plan includes and allows, with ✓/– for each option of its type."""
    features = plan_features(plan)
    rule = rule_for(plan.pricing_mode)
    lines = [f"💰 هزینه: {plan_price_line(plan)}"]
    fee = setup_fee(plan)
    if fee:
        lines.append(f"💳 {SETUP_FEE_LABEL}: {toman(fee)} (یک‌بار هنگام خرید)")
    # 0 is unlimited for every type (old fixed plans may have no volume).
    if int(plan.data_limit or 0) > 0:
        label = "حجم" if rule.volume == "required" else "سقف کل ترافیک"
        lines.append(f"📦 {label}: {format_size(int(plan.data_limit))}")
    else:
        lines.append("📦 حجم: نامحدود")
    if features["expires"] and int(plan.duration or 0) > 0:
        lines.append(f"⏰ مدت: {int(plan.duration)} روز")
    else:
        lines.append("⏰ مدت: بدون انقضا")
    lines.append(f"👥 حداکثر یوزر: {int(plan.max_users or 0) or 'نامحدود'}")
    if features["renewable"] and (int(plan.duration or 0) > 0 or int(plan.data_limit or 0) > 0):
        lines.append("✓ تمدید با همین پلن")
    if features["usage_cap"]:
        lines.append("✓ تعیین سقف مصرف دلخواه")
    if ADDON_DAYS in rule.addons:
        lines.append(_addon_line(features["extra_day_price"], ADDON_NAMES[ADDON_DAYS], "روز"))
    if ADDON_VOLUME in rule.addons:
        lines.append(_addon_line(features["extra_gb_price"], ADDON_NAMES[ADDON_VOLUME], "گیگ"))
    if ADDON_USERS in rule.addons and int(plan.max_users or 0) > 0:
        lines.append(_addon_line(features["extra_user_price"], ADDON_NAMES[ADDON_USERS], "یوزر"))
    return lines


def plan_how_it_works_lines(plan, ctx: GuideContext | None = None) -> list[str]:
    """How the plan behaves, generated from its real settings; add-ons that are off are not mentioned."""
    ctx = ctx or GuideContext()
    features = plan_features(plan)
    mode = plan.pricing_mode
    days = int(plan.duration or 0)
    volume = format_size(int(plan.data_limit or 0)) if int(plan.data_limit or 0) > 0 else ""
    lines: list[str] = []

    if mode in (FIXED, UNLIMITED):
        lines.append(f"• مبلغ {toman(plan.price)} یک‌بار از کیف پول کسر و نمایندگی فوراً ساخته می‌شود.")
        if days:
            volume_part = f" و حجم {volume}" if mode == FIXED and volume else ""
            lines.append(f"• اعتبار {days} روز{volume_part} است.")
        if mode == UNLIMITED or not volume:
            lines.append("• حجم نامحدود است.")
        if days:
            lines.append(
                "• در پایان مدت، نمایندگی منقضی و غیرفعال می‌شود؛ اگر تا "
                f"{ctx.grace_days} روز تمدید نکنید، ادمین و همه یوزرهایش از پنل حذف می‌شوند."
            )
        else:
            lines.append("• این پلن تاریخ انقضا ندارد.")
        renew_parts = [f"{days} روز از تاریخ انقضای فعلی"] if days else []
        if mode == FIXED and volume:
            renew_parts.append(f"{volume} روی حجم فعلی")
        if renew_parts:
            lines.append(
                f"• تمدید فقط با همین پلن و به قیمت فعلی آن است: {' و '.join(renew_parts)} اضافه می‌شود؛ "
                "باقی‌مانده حفظ می‌شود و چیزی ریست نمی‌شود."
            )
    elif mode in (USAGE, HOURLY):
        fee = setup_fee(plan)
        if fee:
            lines.append(f"• {SETUP_FEE_LABEL}: {toman(fee)} یک‌بار هنگام خرید از کیف پول کسر می‌شود.")
        else:
            lines.append("• پرداخت اولیه ندارد.")
        if ctx.min_wallet:
            lines.append(f"• برای خرید، حداقل {toman(ctx.min_wallet)} موجودی کیف پول لازم است.")
        if mode == USAGE:
            lines.append(
                f"• هر دقیقه حجم مصرف‌شده محاسبه و به‌ازای هر گیگ {toman(plan.unit_price)} "
                "(به نسبت مصرف) از کیف پول کسر می‌شود."
            )
        else:
            lines.append(f"• هر دقیقه که پنل فعال است، به نسبت هر ساعت {toman(plan.unit_price)} از کیف پول کسر می‌شود.")
        lines.append("• انقضا ندارد و تمدید لازم نیست.")
        lines.append("• اگر موجودی تمام شود، پنل تعلیق می‌شود و بعد از شارژ کیف پول، خودکار دوباره فعال می‌شود.")
        if mode == HOURLY:
            lines.append("• وقتی پنل را خودتان غیرفعال کنید، هزینه‌ای کسر نمی‌شود.")
        if features["usage_cap"]:
            lines.append("• می‌توانید برای خودتان سقف مصرف تعیین کنید تا بیشتر از آن هزینه نشود.")
        if volume:
            lines.append(f"• سقف کل ترافیک این پلن {volume} است.")
        lines.append("• قیمت از پلن فعلی خوانده می‌شود؛ اگر تغییر کند، از همان لحظه اعمال و به شما اطلاع داده می‌شود.")
    else:
        lines.append("• مبلغ بر اساس حجمی که وارد می‌کنید یک‌بار از کیف پول کسر می‌شود.")

    addon_bits: list[str] = []
    if features["extra_day_price"]:
        addon_bits.append(f"روز اضافه (هر روز {toman(features['extra_day_price'])}؛ حتی بعد از انقضا)")
    if features["extra_gb_price"]:
        addon_bits.append(f"حجم اضافه (هر گیگ {toman(features['extra_gb_price'])}؛ قبل از انقضا)")
    if features["extra_user_price"] and int(plan.max_users or 0) > 0:
        addon_bits.append(f"یوزر اضافه (هر یوزر {toman(features['extra_user_price'])}؛ دائمی)")
    if addon_bits:
        lines.append(f"• هر وقت خواستید می‌توانید بخرید: {'، '.join(addon_bits)}.")
    return lines


# Placeholders an admin can use when rewriting a plan type's buyer guide in the bot texts.
GUIDE_PLACEHOLDERS = {
    "plan_name": "نام پلن",
    "price": "قیمت (بسته، هر گیگ یا هر ساعت)",
    "volume": "حجم یا سقف ترافیک",
    "days": "مدت",
    "max_users": "سقف یوزر",
    "grace_days": "روزهای مهلت پس از انقضا",
    "min_wallet": "حداقل موجودی برای خرید",
    "extra_day_price": "قیمت هر روز اضافه",
    "extra_gb_price": "قیمت هر گیگ اضافه",
    "extra_user_price": "قیمت هر یوزر اضافه",
}


def guide_text_key(mode: str | None) -> str:
    """Bot text key of a plan type's buyer guide; legacy types share the fixed one."""
    return f"reseller_plan_guide_{mode if mode in (FIXED, UNLIMITED, USAGE, HOURLY) else FIXED}"


def guide_placeholders(plan, ctx: GuideContext | None = None) -> dict[str, str]:
    """Values for an admin-written guide; the built-in guide doesn't need them."""
    ctx = ctx or GuideContext()
    limit = int(plan.data_limit or 0)
    return {
        "plan_name": (plan.display_button_text or "").strip().split("\n", 1)[0] or mode_name(plan.pricing_mode),
        "price": plan_price_line(plan),
        "volume": format_size(limit) if limit > 0 else "نامحدود",
        "days": f"{int(plan.duration)} روز" if int(plan.duration or 0) > 0 else "بدون انقضا",
        "max_users": str(int(plan.max_users or 0) or "نامحدود"),
        "grace_days": str(ctx.grace_days),
        "min_wallet": toman(ctx.min_wallet),
        "extra_day_price": toman(addon_price(plan, ADDON_DAYS)),
        "extra_gb_price": toman(addon_price(plan, ADDON_VOLUME)),
        "extra_user_price": toman(addon_price(plan, ADDON_USERS)),
    }


def buyer_plan_guide(plan, ctx: GuideContext | None = None, *, title: str | None = None) -> str:
    """Plan card shown before purchase: includes/allows list plus «این پلن چطور کار می‌کند؟»."""
    header = f"**{title}**\n" if title else ""
    return (
        f"{header}**📋 نوع پلن:** {mode_name(plan.pricing_mode)}\n\n"
        "**✅ این پلن شامل:**\n"
        + "\n".join(plan_includes_lines(plan))
        + "\n\n**❓ این پلن چطور کار می‌کند؟**\n"
        + "\n".join(plan_how_it_works_lines(plan, ctx))
    )


# --------------------------------------------------------------------------------------------
# Accounts: user limits and add-on quantities
# --------------------------------------------------------------------------------------------


def max_users_label(max_users: int | None, extra_users: int | None) -> str:
    """``60`` or ``50 پلن + 10 اضافه`` when slots were bought on top of the plan; «نامحدود» for 0."""
    total = int(max_users or 0)
    if total <= 0:
        return "نامحدود"
    extra = max(0, min(int(extra_users or 0), total))
    if extra <= 0:
        return str(total)
    return f"{total - extra} پلن + {extra} اضافه"


def format_active_minutes(minutes: int | None) -> str:
    """Active time of one hourly charge row, e.g. «1 ساعت و 5 دقیقه»."""
    total = max(0, int(minutes or 0))
    hours, mins = divmod(total, 60)
    parts = []
    if hours:
        parts.append(f"{hours} ساعت")
    if mins or not hours:
        parts.append(f"{mins} دقیقه")
    return " و ".join(parts)


def _expiry_text(stamp: int | None) -> str:
    from app.utils.formatting.dates import timestamp_to_persian_expiry

    return timestamp_to_persian_expiry(int(stamp)) if stamp else "بدون انقضا"


def renew_preview_lines(account, plan, *, current_limit: int, used_traffic: int, now: int) -> list[str]:
    """Before → after of one renewal, computed the same way ``renew_reseller_account`` applies it."""
    lines: list[str] = []
    added_bytes = int(plan.data_limit or 0)
    if added_bytes > 0:
        before = int(current_limit or 0)
        after = (before if before > 0 else int(used_traffic or 0)) + added_bytes
        before_text = format_size(before) if before > 0 else "نامحدود"
        lines.append(f"📦 حجم: {before_text} ← {format_size(after)} (+{format_size(added_bytes)})")
    elif int(current_limit or 0) > 0:
        lines.append(f"📦 حجم: {format_size(int(current_limit))} (بدون تغییر)")
    else:
        lines.append("📦 حجم: نامحدود (بدون تغییر)")
    days = int(plan.duration or 0)
    expiry = int(account.expiration_time or 0)
    if days > 0:
        after_expiry = max(expiry or now, now) + days * 86400
        line = f"⏰ انقضا: {_expiry_text(expiry)} ← {_expiry_text(after_expiry)} (+{days} روز)"
        if expiry and expiry < now:
            line += "\n   (منقضی شده است؛ روزها از امروز حساب می‌شوند و پنل دوباره فعال می‌شود)"
        lines.append(line)
    lines.append(f"👥 سقف یوزر: {max_users_label(account.max_users, account.extra_users)} (بدون تغییر)")
    return lines


def addon_preview_lines(quote, *, expired: bool = False) -> list[str]:
    """Before → after of one add-on purchase from an ``AddonQuote``."""
    if quote.addon == ADDON_DAYS:
        line = f"⏰ انقضا: {_expiry_text(quote.before)} ← {_expiry_text(quote.after)} (+{quote.quantity} روز)"
        if expired:
            line += "\n   (منقضی شده است؛ روزها از امروز حساب می‌شوند و پنل دوباره فعال می‌شود)"
        return [line]
    if quote.addon == ADDON_VOLUME:
        return [f"📦 حجم: {format_size(quote.before)} ← {format_size(quote.after)} (+{quote.quantity} گیگ)"]
    return [f"👥 سقف یوزر: {quote.before} ← {quote.after} (+{quote.quantity} یوزر، دائمی)"]


def addon_current_line(account, addon: str) -> str:
    """The value an add-on changes, as it is now."""
    if addon == ADDON_DAYS:
        return f"⏰ انقضای فعلی: {_expiry_text(account.expiration_time)}"
    if addon == ADDON_VOLUME:
        return f"📦 حجم فعلی: {format_size(int(account.data_limit or 0))}"
    return f"👥 سقف یوزر فعلی: {max_users_label(account.max_users, account.extra_users)}"


def parse_addon_quantity(addon: str, raw: str | None) -> tuple[int | None, str | None]:
    """Validate a typed add-on quantity (days, GB or users). Returns (quantity, error)."""
    value, error = parse_number(raw, allow_zero=False, integer=True)
    if error:
        return None, error
    limit = ADDON_MAX_QUANTITY.get(addon, 0)
    if limit and int(value) > limit:
        return None, f"حداکثر {limit:,} {ADDON_UNITS.get(addon, '')} در هر خرید مجاز است."
    return int(value), None
