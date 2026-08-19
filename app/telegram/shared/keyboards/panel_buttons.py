from __future__ import annotations

from typing import Any

from telethon import Button

from app.db.crud.keyboards import KeyboardButtonCRUD
from app.services.panels.auth import panel_auth_type_label
from app.services.panels.settings import (
    panel_button_enabled,
    panel_display_mode,
    panel_renew_volume_remaining_mode,
    panel_reseller_button_enabled,
    panel_reseller_sale_flag,
    panel_shop_sale_flag,
    panel_time_plans,
    panel_volume_plans,
    panel_webhook_notifications_enabled,
)
from app.telegram.keyboards.common import (
    build_telegram_button_style,
    glass_inline_button,
    styled_callback_button,
)
from app.telegram.keyboards.registry import STYLE_LABELS


def panel_display_keyboard_key(panel_code: int | str) -> str:
    return f"in.panel.display:{panel_code}"


# (callback_key, model_attr, admin_label)
PANEL_MS_BUTTON_TOGGLES: tuple[tuple[str, str, str], ...] = (
    ("zaman", "btn_zaman", "⏰ خرید زمان"),
    ("hajm", "btn_hajm", "♾️ خرید حجم"),
    ("tamdid", "btn_tamdid", "💎 تمدید سرویس"),
    ("change_sub", "btn_change_sub", "🔗 تغییر ساب"),
    ("other_links", "btn_other_links", "➕ لینک‌های دیگر"),
    ("change_link", "btn_change_link", "🔗 تغییر لینک"),
    ("copy_link", "btn_copy_link", "🔗 کپی لینک"),
    ("qr", "btn_qr", "🔘 QRcode"),
    ("transfer", "btn_transfer", "🔎 واگذاری"),
    ("clients", "btn_clients", "🖥 کلاینت‌ها"),
    ("usage_chart", "btn_usage_chart", "📊 نمودار مصرف"),
    ("info", "btn_info", "⚙️ اطلاعات"),
    ("del_service", "btn_del_service", "🗑 حذف کانفیگ"),
)

PANEL_MS_BTN_DEFAULTS: dict[str, bool] = {}


# Reseller account-detail buttons are stored separately from service buttons.
PANEL_MS_RESELLER_BUTTON_TOGGLES: tuple[tuple[str, str], ...] = (
    ("credentials", "🔑 نمایش رمز ورود"),
    ("change_password", "🔐 تغییر رمز عبور"),
    ("toggle_status", "🕹 فعال/غیرفعال سازی پنل"),
    ("usage_report", "📊 گزارش مصرف"),
    ("usage_cap", "📦 محدودیت مصرف"),
    ("buy_user_capacity", "👥 خرید ظرفیت کاربر اضافه"),
    ("delete", "🗑 حذف نمایندگی"),
)


def panel_ms_btn_default(attr: str) -> bool:
    return PANEL_MS_BTN_DEFAULTS.get(attr, True)


def _panel_ms_btn_flag(panel: Any, attr: str) -> str:
    return "✅" if panel_button_enabled(panel, attr) else "❌"


def _panel_ms_reseller_btn_flag(panel: Any, key: str) -> str:
    return "✅" if panel_reseller_button_enabled(panel, key) else "❌"


def panel_ms_buttons_menu_text(panel: Any) -> str:
    return (
        f"📱 **دکمه‌های سرویس من — {panel.name}**\n"
        f"🧷 کد پنل: `{panel.code}`\n\n"
        "وضعیت **این پنل** را برای هر دکمه روشن/خاموش کنید.\n"
        "برای نمایش به کاربر، تنظیم سراسری ربات هم باید فعال باشد."
    )


def build_panel_ms_buttons_menu(panel: Any) -> list:
    code = panel.code
    rows = []
    for i in range(0, len(PANEL_MS_BUTTON_TOGGLES), 2):
        chunk = PANEL_MS_BUTTON_TOGGLES[i : i + 2]
        rows.append(
            [
                Button.inline(
                    f"{label} ({_panel_ms_btn_flag(panel, attr)})",
                    data=f"panel_ms_btn:{key}:{code}",
                )
                for key, attr, label in chunk
            ]
        )
    rows.append([Button.inline("🏢 دکمه‌های نمایندگی", data=f"panel_ms_reseller_header:{code}")])
    for key, label in PANEL_MS_RESELLER_BUTTON_TOGGLES:
        rows.append(
            [
                Button.inline(
                    f"{label} ({_panel_ms_reseller_btn_flag(panel, key)})",
                    data=f"panel_ms_reseller_btn:{key}:{code}",
                )
            ]
        )
    rows.append([glass_inline_button("🔙 بازگشت به پنل", data=f"panel_info:{code}")])
    return rows


async def ensure_panel_display_record(panel) -> None:
    key = panel_display_keyboard_key(panel.code)
    keyboard_crud = KeyboardButtonCRUD()
    if not await keyboard_crud.get_button(key):
        await keyboard_crud.set_button_text(
            key,
            panel.name,
            description=f"دکمه نمایش پنل {panel.name} (خرید و لیست وضعیت)",
        )


async def build_panel_display_button(panel: Any, callback_data: str):
    key = panel_display_keyboard_key(panel.code)
    keyboard_crud = KeyboardButtonCRUD()
    button = await keyboard_crud.get_button(key)
    text = button.button_text if button and button.button_text else panel.name
    style_raw = getattr(button, "button_style", None) if button else None
    icon = getattr(button, "button_icon", None) if button else None
    style_name = None if style_raw == "" else style_raw
    style = build_telegram_button_style(style_name, icon) if (style_name or icon) else None
    return styled_callback_button(text, callback_data, style)


def panel_display_config_text(panel: Any, button_obj) -> str:
    current_text = getattr(button_obj, "button_text", None) or panel.name
    current_style = STYLE_LABELS.get(getattr(button_obj, "button_style", None), "پیش‌فرض (بدون رنگ)")
    if getattr(button_obj, "button_style", None) == "":
        current_style = "بدون رنگ"
    current_icon = getattr(button_obj, "button_icon", None) or "ندارد"
    return (
        f"🎨 **استایل دکمه پنل «{panel.name}»**\n"
        f"🧷 کد: `{panel.code}`\n\n"
        f"📝 متن: {current_text}\n"
        f"🎨 رنگ: {current_style}\n"
        f"🖼 آیکون: {current_icon}\n\n"
        "در **خرید سرویس** و **📉 وضعیت پنل‌ها** با همین استایل نمایش داده می‌شود.\n"
        "یکی از گزینه‌ها را انتخاب کنید:"
    )


def create_panel_display_config_submenu(panel_code: int | str) -> list:
    return [
        [Button.inline("✏️ متن دکمه", data=f"panel_display_edit_text:{panel_code}")],
        [
            Button.inline("آبی", data=f"panel_display_color:{panel_code}:primary"),
            Button.inline("سبز", data=f"panel_display_color:{panel_code}:success"),
            Button.inline("قرمز", data=f"panel_display_color:{panel_code}:danger"),
            Button.inline("—", data=f"panel_display_color:{panel_code}:none"),
        ],
        [Button.inline("🖼 آیکون پریمیوم", data=f"panel_display_icon:{panel_code}")],
        [Button.inline("🧹 حذف آیکون", data=f"panel_display_icon_clear:{panel_code}")],
        [Button.inline("♻️ ریست به نام پنل", data=f"panel_display_reset:{panel_code}")],
        [Button.inline("🔙 بازگشت", data=f"panel_info:{panel_code}")],
    ]


def build_panel_admin_settings_buttons(panel: Any) -> list:
    """English docstring for build_panel_admin_settings_buttons."""
    code = panel.code
    on = "✅" if panel.enable else "❌"
    shop_on = "✅" if panel_shop_sale_flag(panel) else "❌"
    reseller_on = "✅" if panel_reseller_sale_flag(panel) else "❌"
    webhook = "🔔" if panel_webhook_notifications_enabled(panel) else "🤖"
    renew_vol = panel_renew_volume_remaining_mode(panel)
    renew_vol_short = "باقی+ریست" if renew_vol else "جمعی"
    display_mode = panel_display_mode(panel)
    display_short = "⏰ زمان" if display_mode == "duration_first" else "📋 کلاسیک"

    rows = [
        [Button.inline("🎨 استایل دکمه (خرید / لیست)", data=f"edit_panel_display:{code}")],
        [Button.inline(f"⚡ فعال‌سازی پنل ({on})", data=f"panel_toggle_status:{code}")],
        [
            Button.inline(f"🛒 خرید سرویس ({shop_on})", data=f"panel_toggle_shop_sale:{code}"),
            Button.inline(f"🏢 نمایندگی ({reseller_on})", data=f"panel_toggle_reseller_sale:{code}"),
        ],
        [Button.inline("✏️ نام", data=f"change_panel_name:{code}")],
        [Button.inline(f"🔑 ورود ({panel_auth_type_label(panel, short=True)})", data=f"panel_auth_type:{code}")],
        [Button.inline("📦 گروه پیش‌فرض", data=f"change_panel_group:{code}")],
        [Button.inline("🧢 سقف خرید سرویس از این پنل", data=f"panel_user_limit:{code}")],
        [glass_inline_button("📱 دکمه‌های سرویس من", data=f"panel_ms_buttons:{code}")],
        [Button.inline(f"📊 نمایش ({display_short})", data=f"panel_display_mode:{code}")],
        [
            Button.inline(f"📡 اطلاع‌رسانی ({webhook})", data=f"panel_webhook_notifications:{code}"),
            Button.inline(f"📊 تمدید حجم ({renew_vol_short})", data=f"panel_renew_volume_mode:{code}"),
        ],
        [
            Button.inline("🔗 لینک ساب", data=f"panel_subscription_link_mode:{code}"),
            Button.inline("🔗 لینک تکی", data=f"panel_single_config_links:{code}"),
        ],
        [Button.inline("🌐 پیشوند نود", data=f"panel_node_prefixes:{code}")],
        [Button.inline("🧪 تنظیمات تست", data=f"panel_test_settings:{code}")],
        [Button.inline("🧩 خرید دلخواه (حجم/زمان)", data=f"panel_custom_buy:{code}")],
        [Button.inline("👥 خرید ظرفیت کاربر (نمایندگی)", data=f"panel_reseller_capacity:{code}")],
        [
            Button.inline("♾️ پلن‌های حجم اضافه", data=f"panel_volume_plans:{code}"),
            Button.inline("⏰ پلن‌های زمان اضافه", data=f"panel_time_plans:{code}"),
        ],
    ]
    if panel.tunnel_url:
        rows.append([Button.inline("🔄 حذف لینک تانل", data=f"clear_panel_tunnel_url:{code}")])
    else:
        rows.append([Button.inline("➕ لینک تانل", data=f"set_panel_tunnel_url:{code}")])
    rows.append([Button.inline("🔗 مسیر ورود ادمین", data=f"set_panel_login_path:{code}")])
    rows.append([glass_inline_button("📖 آموزش دکمه‌های تنظیمات پنل", data=f"panel_settings_help:{code}")])
    rows.append([Button.inline("❌ حذف پنل", data=f"panel_delete:{code}")])
    rows.append([Button.inline("🔙 لیست پنل‌ها", data="backPanel_list")])
    return rows


async def build_panel_list_rows(panels: list, *, callback_prefix: str = "panel_info") -> list:
    rows = []
    for panel in panels:
        rows.append([await build_panel_display_button(panel, f"{callback_prefix}:{panel.code}")])
    return rows


async def build_buy_panel_rows(panels: list, *, cancel_data: str = "DataCancel", columns: int = 3) -> list:
    from app.telegram.keyboards.buy import buy_cancel_button

    flat = [await build_panel_display_button(panel, f"BuyVPN_{panel.code}") for panel in panels]
    rows = [flat[i : i + columns] for i in range(0, len(flat), columns)]
    rows.append([await buy_cancel_button(cancel_data)])
    return rows


def default_volume_upgrade_button_text(plan: dict[str, Any]) -> str:
    custom = (plan.get("display_button_text") or "").strip()
    tpl = custom if custom else "{gig} گیگ — {price} تومان"
    gb = plan["storage_gb"]
    gig = str(int(gb)) if float(gb) == int(gb) else str(gb)
    return tpl.format(gig=gig, price=f"{int(plan['price']):,}")


def default_time_upgrade_button_text(plan: dict[str, Any]) -> str:
    custom = (plan.get("display_button_text") or "").strip()
    tpl = custom if custom else "{days} روز — {price} تومان"
    return tpl.format(days=plan["duration_days"], price=f"{int(plan['price']):,}")


def resolve_upgrade_plan_button_style(plan: dict[str, Any]):
    style_raw = plan.get("button_style")
    icon = plan.get("button_icon")
    if style_raw is None and not icon:
        return None
    style_name = None if style_raw == "" else style_raw
    if style_name is None and not icon:
        return None
    return build_telegram_button_style(style_name, icon)


def build_volume_upgrade_inline_button(plan: dict[str, Any], service_code, *, data_wrapper=None):
    text = default_volume_upgrade_button_text(plan)
    callback = f"upgSize@{service_code}@{plan['id']}"
    if data_wrapper:
        callback = data_wrapper(callback)
    return styled_callback_button(text, callback, resolve_upgrade_plan_button_style(plan))


def build_time_upgrade_inline_button(plan: dict[str, Any], service_code, *, data_wrapper=None):
    text = default_time_upgrade_button_text(plan)
    callback = f"upgTime@{service_code}@{plan['id']}"
    if data_wrapper:
        callback = data_wrapper(callback)
    return styled_callback_button(text, callback, resolve_upgrade_plan_button_style(plan))


def build_volume_upgrade_tariff_text(plans: list[dict[str, Any]]) -> str:
    lines = ["تعرفه ارتقای حجم سرویس:", ""]
    for index, plan in enumerate(plans):
        prefix = "🔹" if index % 2 == 0 else "🔸"
        lines.append(f"{prefix} {plan['storage_gb']} GB = {int(plan['price']):,} تومان")
    lines.extend(["", "لطفا انتخاب فرمایید چه مقدار میخوایید ارتقا دهید ؟!"])
    return "\n".join(lines)


def build_time_upgrade_tariff_text(plans: list[dict[str, Any]]) -> str:
    lines = ["⏱️ تعرفه زمانی (بدون حجم ترافیک):", ""]
    for plan in plans:
        lines.append(f"• {plan['duration_days']} روز : `{int(plan['price']):,}` تومان")
    lines.extend(["", "👈🏻 برای افزایش مدت زمان اعتبار، انتخاب کنید:"])
    return "\n".join(lines)


def build_volume_upgrade_select_buttons(
    panel,
    service_code,
    back_data,
    *,
    data_wrapper=None,
) -> list:
    rows = [
        [build_volume_upgrade_inline_button(plan, service_code, data_wrapper=data_wrapper)]
        for plan in panel_volume_plans(panel)
    ]
    rows.append([Button.inline("بازگشت", data=back_data)])
    return rows


def build_time_upgrade_select_buttons(
    panel,
    service_code,
    back_data,
    *,
    data_wrapper=None,
) -> list:
    rows = [
        [build_time_upgrade_inline_button(plan, service_code, data_wrapper=data_wrapper)]
        for plan in panel_time_plans(panel)
    ]
    rows.append([Button.inline("بازگشت", data=back_data)])
    return rows


def panel_volume_plans_admin_text(panel: Any) -> str:
    plans = panel_volume_plans(panel)
    lines = [
        f"♾️ **پلن‌های حجم اضافه — {panel.name}**",
        f"🧷 کد پنل: `{panel.code}`",
        f"📦 تعداد: `{len(plans)}`",
        "",
        "کمترین حجم در لیست خرید اول نمایش داده می‌شود.",
    ]
    if not plans:
        lines.append("\n⚠️ هنوز پلنی تعریف نشده؛ دکمه حجم اضافه برای این پنل نمایش داده نمی‌شود.")
    return "\n".join(lines)


def panel_time_plans_admin_text(panel: Any) -> str:
    plans = panel_time_plans(panel)
    lines = [
        f"⏰ **پلن‌های زمان اضافه — {panel.name}**",
        f"🧷 کد پنل: `{panel.code}`",
        f"📦 تعداد: `{len(plans)}`",
        "",
        "کمترین تعداد روز در لیست خرید اول نمایش داده می‌شود.",
    ]
    if not plans:
        lines.append("\n⚠️ هنوز پلنی تعریف نشده؛ دکمه زمان اضافه برای این پنل نمایش داده نمی‌شود.")
    return "\n".join(lines)


def build_panel_volume_plans_admin_buttons(panel: Any) -> list:
    code = panel.code
    rows = [
        [Button.inline("➕ افزودن پلن حجم", data=f"panel_add_volume_plan:{code}")],
    ]
    for plan in panel_volume_plans(panel):
        text = default_volume_upgrade_button_text(plan)
        rows.append(
            [
                styled_callback_button(
                    text,
                    f"panel_volume_plan:{code}:{plan['id']}",
                    resolve_upgrade_plan_button_style(plan),
                )
            ]
        )
    rows.append([Button.inline("🔙 بازگشت به پنل", data=f"panel_info:{code}")])
    return rows


def build_panel_time_plans_admin_buttons(panel: Any) -> list:
    code = panel.code
    rows = [
        [Button.inline("➕ افزودن پلن زمان", data=f"panel_add_time_plan:{code}")],
    ]
    for plan in panel_time_plans(panel):
        text = default_time_upgrade_button_text(plan)
        rows.append(
            [
                styled_callback_button(
                    text,
                    f"panel_time_plan:{code}:{plan['id']}",
                    resolve_upgrade_plan_button_style(plan),
                )
            ]
        )
    rows.append([Button.inline("🔙 بازگشت به پنل", data=f"panel_info:{code}")])
    return rows


def panel_volume_plan_info_text(panel: Any, plan: dict[str, Any]) -> str:
    current_text = default_volume_upgrade_button_text(plan)
    current_style = STYLE_LABELS.get(plan.get("button_style"), "پیش‌فرض (بدون رنگ)")
    if plan.get("button_style") == "":
        current_style = "بدون رنگ"
    current_icon = plan.get("button_icon") or "ندارد"
    return (
        f"♾️ **پلن حجم اضافه #{plan['id']}**\n"
        f"📊 پنل: {panel.name} (`{panel.code}`)\n\n"
        f"💾 حجم: `{plan['storage_gb']}` گیگ\n"
        f"💰 قیمت: `{int(plan['price']):,}` تومان\n\n"
        f"📝 متن دکمه: {current_text}\n"
        f"🎨 رنگ: {current_style}\n"
        f"🖼 آیکون: {current_icon}"
    )


def panel_time_plan_info_text(panel: Any, plan: dict[str, Any]) -> str:
    current_text = default_time_upgrade_button_text(plan)
    current_style = STYLE_LABELS.get(plan.get("button_style"), "پیش‌فرض (بدون رنگ)")
    if plan.get("button_style") == "":
        current_style = "بدون رنگ"
    current_icon = plan.get("button_icon") or "ندارد"
    return (
        f"⏰ **پلن زمان اضافه #{plan['id']}**\n"
        f"📊 پنل: {panel.name} (`{panel.code}`)\n\n"
        f"📅 مدت: `{plan['duration_days']}` روز\n"
        f"💰 قیمت: `{int(plan['price']):,}` تومان\n\n"
        f"📝 متن دکمه: {current_text}\n"
        f"🎨 رنگ: {current_style}\n"
        f"🖼 آیکون: {current_icon}"
    )


def build_panel_volume_plan_info_buttons(panel_code: int | str, plan_id: int) -> list:
    return [
        [
            Button.inline("✏️ ویرایش حجم", data=f"panel_edit_volume_storage:{panel_code}:{plan_id}"),
            Button.inline("✏️ ویرایش قیمت", data=f"panel_edit_volume_price:{panel_code}:{plan_id}"),
        ],
        [Button.inline("🎨 تنظیم دکمه نمایش", data=f"edit_volume_plan_display:{panel_code}:{plan_id}")],
        [Button.inline("🗑 حذف پلن", data=f"panel_delete_volume_plan:{panel_code}:{plan_id}")],
        [Button.inline("🔙 بازگشت", data=f"panel_volume_plans:{panel_code}")],
    ]


def build_panel_time_plan_info_buttons(panel_code: int | str, plan_id: int) -> list:
    return [
        [
            Button.inline("✏️ ویرایش مدت", data=f"panel_edit_time_duration:{panel_code}:{plan_id}"),
            Button.inline("✏️ ویرایش قیمت", data=f"panel_edit_time_price:{panel_code}:{plan_id}"),
        ],
        [Button.inline("🎨 تنظیم دکمه نمایش", data=f"edit_time_plan_display:{panel_code}:{plan_id}")],
        [Button.inline("🗑 حذف پلن", data=f"panel_delete_time_plan:{panel_code}:{plan_id}")],
        [Button.inline("🔙 بازگشت", data=f"panel_time_plans:{panel_code}")],
    ]


def volume_plan_display_config_text(panel: Any, plan: dict[str, Any]) -> str:
    current_text = default_volume_upgrade_button_text(plan)
    current_style = STYLE_LABELS.get(plan.get("button_style"), "پیش‌فرض (بدون رنگ)")
    if plan.get("button_style") == "":
        current_style = "بدون رنگ"
    current_icon = plan.get("button_icon") or "ندارد"
    return (
        f"🎨 **تنظیم دکمه حجم اضافه #{plan['id']}**\n"
        f"📊 پنل: {panel.name}\n\n"
        f"📝 متن نمایش: {current_text}\n"
        f"🎨 رنگ: {current_style}\n"
        f"🖼 آیکون: {current_icon}\n\n"
        "یکی از گزینه‌های زیر را انتخاب کنید:"
    )


def time_plan_display_config_text(panel: Any, plan: dict[str, Any]) -> str:
    current_text = default_time_upgrade_button_text(plan)
    current_style = STYLE_LABELS.get(plan.get("button_style"), "پیش‌فرض (بدون رنگ)")
    if plan.get("button_style") == "":
        current_style = "بدون رنگ"
    current_icon = plan.get("button_icon") or "ندارد"
    return (
        f"🎨 **تنظیم دکمه زمان اضافه #{plan['id']}**\n"
        f"📊 پنل: {panel.name}\n\n"
        f"📝 متن نمایش: {current_text}\n"
        f"🎨 رنگ: {current_style}\n"
        f"🖼 آیکون: {current_icon}\n\n"
        "یکی از گزینه‌های زیر را انتخاب کنید:"
    )


def create_volume_plan_display_config_submenu(panel_code: int | str, plan_id: int) -> list:
    return [
        [Button.inline("✏️ متن دکمه", data=f"volume_plan_btn_edit_text:{panel_code}:{plan_id}")],
        [
            Button.inline("آبی", data=f"volume_plan_btn_color:{panel_code}:{plan_id}:primary"),
            Button.inline("سبز", data=f"volume_plan_btn_color:{panel_code}:{plan_id}:success"),
            Button.inline("قرمز", data=f"volume_plan_btn_color:{panel_code}:{plan_id}:danger"),
            Button.inline("—", data=f"volume_plan_btn_color:{panel_code}:{plan_id}:none"),
        ],
        [Button.inline("🖼 آیکون پریمیوم", data=f"volume_plan_btn_icon:{panel_code}:{plan_id}")],
        [Button.inline("🧹 حذف آیکون", data=f"volume_plan_btn_icon_clear:{panel_code}:{plan_id}")],
        [Button.inline("♻️ ریست تنظیمات نمایش", data=f"volume_plan_btn_display_reset:{panel_code}:{plan_id}")],
        [Button.inline("🔙 بازگشت", data=f"panel_volume_plan:{panel_code}:{plan_id}")],
    ]


def create_time_plan_display_config_submenu(panel_code: int | str, plan_id: int) -> list:
    return [
        [Button.inline("✏️ متن دکمه", data=f"time_plan_btn_edit_text:{panel_code}:{plan_id}")],
        [
            Button.inline("آبی", data=f"time_plan_btn_color:{panel_code}:{plan_id}:primary"),
            Button.inline("سبز", data=f"time_plan_btn_color:{panel_code}:{plan_id}:success"),
            Button.inline("قرمز", data=f"time_plan_btn_color:{panel_code}:{plan_id}:danger"),
            Button.inline("—", data=f"time_plan_btn_color:{panel_code}:{plan_id}:none"),
        ],
        [Button.inline("🖼 آیکون پریمیوم", data=f"time_plan_btn_icon:{panel_code}:{plan_id}")],
        [Button.inline("🧹 حذف آیکون", data=f"time_plan_btn_icon_clear:{panel_code}:{plan_id}")],
        [Button.inline("♻️ ریست تنظیمات نمایش", data=f"time_plan_btn_display_reset:{panel_code}:{plan_id}")],
        [Button.inline("🔙 بازگشت", data=f"panel_time_plan:{panel_code}:{plan_id}")],
    ]
