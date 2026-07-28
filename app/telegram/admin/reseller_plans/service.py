"""Shared helpers for admin reseller plans."""

from telethon import Button

from app.db.crud.panels import PanelsManager
from app.db.crud.reseller_accounts import ResellerAccountCRUD
from app.services.billing.reseller_pricing import (
    format_reseller_plan_admin_list_label,
    format_reseller_plan_price_short,
    pricing_mode_label,
    pricing_mode_short_label,
    volume_unit_label,
)
from app.telegram.keyboards.common import styled_callback_button
from app.telegram.keyboards.registry import STYLE_LABELS
from app.telegram.shared.keyboards.plan_buttons import resolve_plan_button_style
from app.telegram.user.reseller.helpers import format_plan_button_text
from app.utils.formatting.traffic import format_size


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
    return pricing_mode_short_label(plan.pricing_mode)


def format_reseller_plan_list_label(plan) -> str:
    return format_reseller_plan_admin_list_label(plan)


def format_reseller_import_plan_button(plan) -> str:
    mode = pricing_mode_short_label(plan.pricing_mode)
    status = "✅" if plan.enable else "❌"
    custom = (plan.display_button_text or "").strip()
    name = custom.split("\n", 1)[0].strip()[:20] if custom else ""
    price = format_reseller_plan_price_short(plan)
    if name:
        return f"#{plan.id} {name} · {mode} · {price} {status}"
    return f"#{plan.id} · {mode} · {price} {status}"


async def format_reseller_plan_detail(plan) -> str:
    panel = await PanelsManager().get_panel_by_code(code=plan.panel_code)
    panel_name = panel.name if panel else str(plan.panel_code)
    title = reseller_plan_title(plan)
    lines = [
        f"**پلن #{plan.id}** — {title}",
        f"**📛 پنل:** {panel_name}",
        f"**📋 نوع:** {pricing_mode_label(plan.pricing_mode)}",
        f"**🛡 نقش:** {plan.role_name or plan.role_id}",
        f"**⚙️ وضعیت:** {'✅ فعال' if plan.enable else '❌ غیرفعال'}",
    ]
    if plan.pricing_mode == "fixed":
        lines.append(f"**💰 قیمت:** {int(plan.price):,} تومان")
    else:
        lines.append(f"**💰 قیمت واحد:** {int(plan.unit_price):,} تومان")
        if plan.pricing_mode in ("per_gb", "per_tb"):
            lines.append(
                f"**📦 محدوده حجم:** {plan.min_volume:g} — {plan.max_volume:g} {volume_unit_label(plan.pricing_mode)}"
            )
    if plan.data_limit:
        lines.append(f"**📥 سقف ترافیک:** {format_size(plan.data_limit)}")
    if plan.max_users:
        lines.append(f"**👥 سقف یوزر:** {plan.max_users}")
    if plan.duration:
        lines.append(f"**⏰ مدت:** {plan.duration} روز")

    btn_text = (plan.display_button_text or "").strip() or format_plan_button_text(plan)
    style_label = STYLE_LABELS.get(plan.button_style, "پیش‌فرض")
    if plan.button_style == "":
        style_label = "بدون رنگ"
    icon_label = str(plan.button_icon) if plan.button_icon else "ندارد"
    lines.extend(
        [
            "",
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


def plan_manage_buttons(plan_id: int, panel_code: int) -> list:
    return [
        [
            Button.inline("✏️ قیمت", data=f"ResellerPlanEditPrice_{plan_id}"),
            Button.inline("🔄 وضعیت", data=f"ResellerPlanToggle_{plan_id}"),
        ],
        [Button.inline("🎨 نمایش دکمه", data=f"ResellerPlanDisplay_{plan_id}")],
        [Button.inline("🗑 حذف", data=f"ResellerPlanDelete_{plan_id}")],
        [Button.inline("🔙 بازگشت", data=f"ResellerPlanManage_{panel_code}")],
    ]
