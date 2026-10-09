"""Shared helpers for admin reseller plans."""

from telethon import Button

from app.db.crud.panels import PanelsManager
from app.db.crud.reseller_accounts import ResellerAccountCRUD
from app.services.billing.reseller_pricing import (
    format_reseller_plan_price_short,
    volume_unit_label,
)
from app.services.reseller.plan_rules import ADDON_PRICE_FIELDS, rule_for
from app.telegram.keyboards.common import styled_callback_button
from app.telegram.keyboards.registry import STYLE_LABELS
from app.telegram.shared.keyboards.plan_buttons import resolve_plan_button_style
from app.telegram.shared.reseller_plan_guides import (
    ADDON_NAMES,
    HOURLY,
    SETUP_FEE_LABEL,
    USAGE,
    admin_guide_summary,
    admin_mode_name,
    admin_mode_short_name,
    editable_fields,
    field_label,
    format_field_value,
    is_creatable,
    setup_fee,
)
from app.telegram.user.reseller.helpers import format_plan_button_text


def reseller_plan_main_menu_buttons() -> list:
    return [
        [Button.inline("➕ ساخت پلن نمایندگی", data="ResellerPlanAddPanel")],
        [Button.inline("📋 مدیریت پلن‌ها", data="ResellerPlanManagePanel")],
        [Button.inline("➕ افزودن ادمین موجود", data="ResellerImportPanel")],
        [Button.inline("❌ بستن", data="ResellerPlanCancel")],
    ]


def reseller_plan_title(plan) -> str:
    custom = (plan.display_button_text or "").strip()
    if custom:
        return custom.split("\n", 1)[0].strip()
    return admin_mode_short_name(plan.pricing_mode)


def format_reseller_plan_list_label(plan) -> str:
    """Admin list label: name, type, price and on/off, so plans of different types are told apart."""
    return format_reseller_import_plan_button(plan)


def format_reseller_import_plan_button(plan) -> str:
    mode = admin_mode_short_name(plan.pricing_mode)
    status = "✅" if plan.enable else "❌"
    custom = (plan.display_button_text or "").strip()
    name = custom.split("\n", 1)[0].strip()[:20] if custom else ""
    price = format_reseller_plan_price_short(plan)
    if name:
        return f"#{plan.id} {name} · {mode} · {price} {status}"
    return f"#{plan.id} · {mode} · {price} {status}"


def plan_type_text(plan) -> str:
    name = admin_mode_name(plan.pricing_mode)
    return name if is_creatable(plan.pricing_mode) else f"{name} — فقط ویرایش، ساخت پلن جدید از این نوع ممکن نیست"


def plan_values_lines(plan) -> list[str]:
    """Prices, limits and add-ons of a stored plan, labelled for its type."""
    mode = plan.pricing_mode
    rule = rule_for(mode)
    lines = [
        f"**💰 {field_label(rule.price_field, mode)}:** {format_field_value('price', getattr(plan, rule.price_field))}"
    ]
    if mode in ("per_gb", "per_tb"):
        lines.append(f"**📦 محدوده حجم:** {plan.min_volume:g} — {plan.max_volume:g} {volume_unit_label(mode)}")
    if rule.volume != "none" or plan.data_limit:
        lines.append(f"**📥 {field_label('data_limit', mode)}:** {format_field_value('data_limit', plan.data_limit)}")
    lines.append(f"**👥 حداکثر یوزر:** {format_field_value('max_users', plan.max_users)}")
    if rule.duration == "required" or plan.duration:
        lines.append(f"**⏰ مدت:** {format_field_value('duration', plan.duration)}")
    if mode in (USAGE, HOURLY):
        fee = setup_fee(plan)
        lines.append(f"**💳 {SETUP_FEE_LABEL}:** {fee:,} تومان" if fee else "**💳 پرداخت اولیه:** ندارد")
    if rule.addons:
        lines.append("")
        lines.append("**🧩 افزودنی‌ها (0 = خاموش):**")
        for addon in rule.addons:
            field = ADDON_PRICE_FIELDS[addon]
            lines.append(f"• {ADDON_NAMES[addon]}: {format_field_value(field, getattr(plan, field, 0))}")
    return lines


async def format_reseller_plan_detail(plan) -> str:
    panel = await PanelsManager().get_panel_by_code(code=plan.panel_code)
    panel_name = panel.name if panel else str(plan.panel_code)
    title = reseller_plan_title(plan)
    lines = [
        f"**پلن #{plan.id}** — {title}",
        f"**📛 پنل:** {panel_name}",
        f"**📋 نوع:** {plan_type_text(plan)}",
        f"**🛡 نقش:** {plan.role_name or plan.role_id}",
        f"**⚙️ وضعیت:** {'✅ فعال' if plan.enable else '❌ غیرفعال'}",
        "",
        *plan_values_lines(plan),
        "",
        f"**ℹ️ خلاصه راهنما:** {admin_guide_summary(plan)}",
        "",
    ]

    btn_text = (plan.display_button_text or "").strip() or format_plan_button_text(plan)
    style_label = STYLE_LABELS.get(plan.button_style, "پیش‌فرض")
    if plan.button_style == "":
        style_label = "بدون رنگ"
    icon_label = str(plan.button_icon) if plan.button_icon else "ندارد"
    lines.extend(
        [
            "**🎨 نمایش دکمه خرید:**",
            f"• متن: `{btn_text}`",
            f"• رنگ: {style_label}",
            f"• آیکون: {icon_label}",
        ]
    )

    linked = await ResellerAccountCRUD().count_accounts_by_plan(plan.id)
    if linked:
        lines.append(f"\n**🔗 نمایندگی‌های متصل:** {linked} (قابل حذف نیست)")
    return "\n".join(lines)


def reseller_plan_display_config_text(plan) -> str:
    btn_text = (plan.display_button_text or "").strip() or format_plan_button_text(plan)
    style_label = STYLE_LABELS.get(plan.button_style, "پیش‌فرض (بدون رنگ)")
    if plan.button_style == "":
        style_label = "بدون رنگ"
    icon_label = plan.button_icon or "ندارد"
    return (
        f"🎨 **تنظیم دکمه پلن نمایندگی #{plan.id}**\n\n"
        f"📝 متن نمایش: `{btn_text}`\n"
        f"🎨 رنگ: {style_label}\n"
        f"🖼 آیکون: {icon_label}\n\n"
        "متن خالی = قالب خودکار بر اساس نوع پلن.\n"
        "یکی از گزینه‌های زیر را انتخاب کنید:"
    )


def reseller_plan_display_buttons(plan_id: int, panel_code: int) -> list:
    return [
        [Button.inline("✏️ متن دکمه", data=f"ResellerPlanBtnText_{plan_id}")],
        [
            Button.inline("آبی", data=f"ResellerPlanBtnColor_{plan_id}:primary"),
            Button.inline("سبز", data=f"ResellerPlanBtnColor_{plan_id}:success"),
            Button.inline("قرمز", data=f"ResellerPlanBtnColor_{plan_id}:danger"),
            Button.inline("—", data=f"ResellerPlanBtnColor_{plan_id}:none"),
        ],
        [Button.inline("🖼 آیکون ایموجی پریمیوم", data=f"ResellerPlanBtnIcon_{plan_id}")],
        [Button.inline("🧹 حذف آیکون", data=f"ResellerPlanBtnIconClear_{plan_id}")],
        [Button.inline("♻️ ریست نمایش", data=f"ResellerPlanBtnReset_{plan_id}")],
        [Button.inline("🔙 بازگشت", data=f"ResellerPlanView_{plan_id}")],
    ]


def build_reseller_plan_list_button(plan):
    text = format_reseller_plan_list_label(plan)
    style = resolve_plan_button_style(plan)
    return styled_callback_button(text, f"ResellerPlanView_{plan.id}", style)


_EDIT_BUTTON_LABELS = {
    "price": "قیمت",
    "max_users": "سقف یوزر",
    "duration": "مدت",
    "addon_day_price": "قیمت روز اضافه",
    "addon_gb_price": "قیمت حجم اضافه",
    "addon_user_price": "قیمت یوزر اضافه",
}


def edit_button_label(field: str, mode: str) -> str:
    if field == "price" and mode in (USAGE, HOURLY):
        return "هزینه راه‌اندازی"
    if field == "unit_price":
        return "قیمت هر ساعت" if mode == HOURLY else "قیمت هر گیگ" if mode == USAGE else "قیمت واحد"
    if field == "data_limit":
        return "حجم" if rule_for(mode).volume == "required" else "سقف ترافیک"
    return _EDIT_BUTTON_LABELS.get(field, field)


def plan_manage_buttons(plan) -> list:
    plan_id = plan.id
    edit_buttons = [
        Button.inline(
            f"✏️ {edit_button_label(field, plan.pricing_mode)}", data=f"ResellerPlanEditField_{plan_id}:{field}"
        )
        for field in editable_fields(plan.pricing_mode, plan)
    ]
    rows = [edit_buttons[i : i + 2] for i in range(0, len(edit_buttons), 2)]
    rows.extend(
        [
            [
                Button.inline("🔄 وضعیت", data=f"ResellerPlanToggle_{plan_id}"),
                Button.inline("🎨 نمایش دکمه", data=f"ResellerPlanDisplay_{plan_id}"),
            ],
            [Button.inline("🗑 حذف", data=f"ResellerPlanDelete_{plan_id}")],
            [Button.inline("🔙 بازگشت", data=f"ResellerPlanManage_{plan.panel_code}")],
        ]
    )
    return rows
