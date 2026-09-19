from __future__ import annotations

from typing import Any

from telethon import Button

from app.services.panels.settings import panel_display_mode
from app.telegram.keyboards.common import build_telegram_button_style, styled_callback_button
from app.telegram.keyboards.registry import STYLE_LABELS
from app.utils.formatting.conversions import convert_storage

PLAN_BUTTON_CONTEXTS = frozenset({"buy", "tamdid", "admin_list"})


def _format_storage_number(storage: float) -> str:
    if isinstance(storage, float) and storage.is_integer():
        return str(int(storage))
    if storage == int(storage):
        return str(int(storage))
    return str(storage)


def build_default_admin_plan_list_text(plan: Any) -> str:
    type_label = {
        "volume": "📊 حجمی",
        "unlimited_volume": "♾️ نامحدود",
        "fair_usage": "⚖️ مصرف منصفانه",
    }.get(getattr(plan, "plan_type", "volume"), "📊 حجمی")
    duration_text = "نامحدود" if not plan.duration else f"{plan.duration} روز"
    return (
        f"💾 {_format_storage_number(plan.storage)} گیگ | "
        f"💰 {int(plan.price):,} تومان | "
        f"⏳ {duration_text} | "
        f"{type_label}"
    )


async def build_plan_admin_list_button(plan: Any, callback_data, *, persian_digits=None):
    custom_text = getattr(plan, "display_button_text", None)
    if custom_text:
        text = custom_text
    else:
        text = build_default_admin_plan_list_text(plan)
        if persian_digits:
            text = persian_digits(text)
    style = resolve_plan_button_style(plan)
    return styled_callback_button(text, callback_data, style)


def build_default_plan_button_text(plan: Any, display_mode: str, context: str) -> str:
    plan_name = convert_storage(
        plan.storage,
        getattr(plan, "plan_type", None),
        getattr(plan, "data_limit_reset_strategy", None),
        for_button=True,
    )
    ip_limit = getattr(plan, "ip_limit", 0) or 0
    duration_text = "نامحدود" if not plan.duration else f"{plan.duration}روزه"

    price_text = f"{plan.price // 1000:,.0f} هزارتومان" if context == "buy" else f"{plan.price // 1000:,.0f} تومان"

    if context == "tamdid":
        if ip_limit > 0:
            return f"🗳 {plan_name} - {duration_text} - [{ip_limit}] کاربره - {price_text}"
        return f"🗳 {plan_name} - {duration_text} - {price_text}"

    # buy
    if display_mode == "classic":
        if ip_limit > 0:
            return f"🗳 {plan_name} {duration_text} [{ip_limit}] کاربره {price_text}"
        return f"🗳 {plan_name} {duration_text} {price_text}"
    if ip_limit > 0:
        return f"🗳 {plan_name} [{ip_limit}] کاربره {price_text}"
    return f"🗳 {plan_name} {price_text}"


def resolve_plan_button_style(plan: Any):
    style_raw = getattr(plan, "button_style", None)
    icon = getattr(plan, "button_icon", None)
    if style_raw is None and icon is None:
        return None
    style_name = None if style_raw == "" else style_raw
    if style_name is None and icon is None:
        return None
    return build_telegram_button_style(style_name, icon)


def plan_has_display_override(plan: Any) -> bool:
    return bool(
        getattr(plan, "display_button_text", None)
        or getattr(plan, "button_style", None) is not None
        or getattr(plan, "button_icon", None)
    )


async def build_plan_inline_button(
    plan: Any,
    panel: Any,
    callback_data,
    *,
    context: str = "buy",
):
    display_mode = panel_display_mode(panel) if panel else "classic"
    custom_text = getattr(plan, "display_button_text", None)
    text = custom_text or build_default_plan_button_text(plan, display_mode, context)
    style = resolve_plan_button_style(plan)
    return styled_callback_button(text, callback_data, style)


def plan_display_config_text(plan: Any, panel: Any | None) -> str:
    display_mode = panel_display_mode(panel) if panel else "classic"
    current_text = getattr(plan, "display_button_text", None) or build_default_plan_button_text(
        plan, display_mode, "buy"
    )
    current_style = STYLE_LABELS.get(getattr(plan, "button_style", None), "پیش‌فرض (بدون رنگ)")
    if getattr(plan, "button_style", None) == "":
        current_style = "بدون رنگ"
    current_icon = getattr(plan, "button_icon", None) or "ندارد"
    return (
        f"🎨 **تنظیم دکمه نمایش پلن #{plan.id}**\n\n"
        f"📝 متن نمایش: {current_text}\n"
        f"🎨 رنگ: {current_style}\n"
        f"🖼 آیکون: {current_icon}\n\n"
        "متن خالی = استفاده از قالب خودکار (حالت کلاسیک).\n"
        "یکی از گزینه‌های زیر را انتخاب کنید:"
    )


def create_plan_display_config_submenu(plan_id: int, current_page: int = 1) -> list:
    return [
        [Button.inline("✏️ متن دکمه", data=f"plan_btn_edit_text:{plan_id}:{current_page}")],
        [
            Button.inline("آبی", data=f"plan_btn_color:{plan_id}:{current_page}:primary"),
            Button.inline("سبز", data=f"plan_btn_color:{plan_id}:{current_page}:success"),
            Button.inline("قرمز", data=f"plan_btn_color:{plan_id}:{current_page}:danger"),
            Button.inline("—", data=f"plan_btn_color:{plan_id}:{current_page}:none"),
        ],
        [Button.inline("🖼 آیکون ایموجی پریمیوم", data=f"plan_btn_icon:{plan_id}:{current_page}")],
        [Button.inline("🧹 حذف آیکون", data=f"plan_btn_icon_clear:{plan_id}:{current_page}")],
        [Button.inline("♻️ ریست تنظیمات نمایش", data=f"plan_btn_display_reset:{plan_id}:{current_page}")],
        [Button.inline("🔙 بازگشت", data=f"plan_info:{plan_id}:{current_page}")],
    ]
