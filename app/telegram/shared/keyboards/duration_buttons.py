from __future__ import annotations

from collections.abc import Callable
from typing import Any

from telethon import Button

from app.db.crud.keyboards import KeyboardButtonCRUD
from app.db.crud.plans import PlanManager
from app.telegram.keyboards.common import build_telegram_button_style, styled_callback_button
from app.telegram.keyboards.registry import STYLE_LABELS


def duration_keyboard_key(panel_code: int | str, duration: int) -> str:
    return f"in.duration:{panel_code}:{duration}"


def duration_keyboard_key_prefix(panel_code: int | str) -> str:
    return f"in.duration:{panel_code}:"


def parse_duration_from_keyboard_key(button_key: str, panel_code: int | str) -> int | None:
    prefix = duration_keyboard_key_prefix(panel_code)
    if not button_key.startswith(prefix):
        return None
    suffix = button_key[len(prefix) :]
    try:
        return int(suffix)
    except ValueError:
        return None


async def get_orphan_duration_values(panel_code: int | str, active_durations: set[int] | None = None) -> list[int]:
    if active_durations is None:
        active_durations = set(await PlanManager().get_unique_durations(int(panel_code)))
    keyboard_crud = KeyboardButtonCRUD()
    stored = await keyboard_crud.get_buttons_by_key_prefix(duration_keyboard_key_prefix(panel_code))
    orphans: list[int] = []
    for button in stored:
        duration = parse_duration_from_keyboard_key(button.button_key, panel_code)
        if duration is not None and duration not in active_durations:
            orphans.append(duration)
    return sorted(set(orphans))


async def cleanup_duration_button_after_plan_delete(panel_code: int | str, duration: int) -> bool:
    remaining = await PlanManager().get_unique_durations(int(panel_code))
    if duration in remaining:
        return False
    return await KeyboardButtonCRUD().delete_button(duration_keyboard_key(panel_code, duration))


async def cleanup_all_orphan_duration_buttons(panel_code: int | str) -> int:
    orphans = await get_orphan_duration_values(panel_code)
    keyboard_crud = KeyboardButtonCRUD()
    deleted = 0
    for duration in orphans:
        if await keyboard_crud.delete_button(duration_keyboard_key(panel_code, duration)):
            deleted += 1
    return deleted


async def build_manage_duration_buttons_view(panel_code: int | str) -> tuple[str, list]:
    panel_code = int(panel_code)
    active_durations = sorted(await PlanManager().get_unique_durations(panel_code))
    orphan_durations = await get_orphan_duration_values(panel_code, set(active_durations))
    keyboard_crud = KeyboardButtonCRUD()

    lines = [f"🎨 **دکمه‌های مدت زمان — پنل `{panel_code}`**", ""]
    rows: list = []

    if active_durations:
        lines.append("**✅ مدت‌های دارای پلن** (برای ویرایش استایل بزنید):")
        for duration in active_durations:
            rows.append(
                [
                    await build_duration_inline_button(
                        panel_code,
                        duration,
                        f"edit_duration_display:{panel_code}:{duration}",
                        context="buy",
                    )
                ]
            )
    else:
        lines.append("⚠️ فعلاً هیچ پلنی برای این پنل ثبت نشده.")

    if orphan_durations:
        lines.append("")
        lines.append(f"**🗑 بدون پلن ({len(orphan_durations)})** — تنظیمات اضافی در دیتابیس:")
        for duration in orphan_durations:
            btn_obj = await keyboard_crud.get_button(duration_keyboard_key(panel_code, duration))
            label = (btn_obj.button_text if btn_obj and btn_obj.button_text else f"{duration} روزه").strip()
            rows.append(
                [
                    Button.inline(
                        f"🗑 {label} — حذف تنظیمات",
                        data=f"delete_orphan_duration:{panel_code}:{duration}",
                    )
                ]
            )
        rows.append([Button.inline("🧹 پاکسازی همه بدون پلن", data=f"CleanupOrphanDurationButtons_{panel_code}")])

    lines.append("")
    lines.append("روی مدت‌های دارای پلن بزنید تا متن، رنگ و آیکون را تنظیم کنید.")
    rows.append([Button.inline("🔙 بازگشت", data=f"ManagePlans_{panel_code}")])
    return "\n".join(lines), rows


async def ensure_duration_button_record(panel_code: int | str, duration: int) -> None:
    key = duration_keyboard_key(panel_code, duration)
    keyboard_crud = KeyboardButtonCRUD()
    if not await keyboard_crud.get_button(key):
        await keyboard_crud.set_button_text(
            key,
            build_default_duration_button_text(duration, "buy"),
            description=f"دکمه مدت {duration} روز — پنل {panel_code} (زمان اول)",
        )


def build_default_duration_button_text(duration: int, context: str = "buy") -> str:
    prefix = "📅" if context == "buy" else "⏰"
    return f"{prefix} {duration} روزه"


async def _get_duration_button_config(panel_code: int | str, duration: int, context: str) -> tuple[str, Any]:
    key = duration_keyboard_key(panel_code, duration)
    keyboard_crud = KeyboardButtonCRUD()
    button = await keyboard_crud.get_button(key)
    default_text = build_default_duration_button_text(duration, context)
    text = button.button_text if button and button.button_text else default_text
    style_raw = getattr(button, "button_style", None) if button else None
    icon = getattr(button, "button_icon", None) if button else None
    style_name = None if style_raw == "" else style_raw
    style = build_telegram_button_style(style_name, icon) if (style_name or icon) else None
    return text, style


async def build_duration_inline_button(
    panel_code: int | str,
    duration: int,
    callback_data,
    *,
    context: str = "buy",
):
    text, style = await _get_duration_button_config(panel_code, duration, context)
    return styled_callback_button(text, callback_data, style)


async def build_duration_selection_button_rows(
    panel_code: int | str,
    duration_groups: dict,
    *,
    context: str,
    make_callback: Callable[[int], str],
    back_row: list,
) -> list:
    duration_buttons = []
    group_items = sorted(duration_groups.items(), key=lambda item: item[1][0])
    for i in range(0, len(group_items), 2):
        row = []
        for offset in (0, 1):
            if i + offset >= len(group_items):
                continue
            duration_value = group_items[i + offset][1][0]
            row.append(
                await build_duration_inline_button(
                    panel_code,
                    duration_value,
                    make_callback(duration_value),
                    context=context,
                )
            )
        duration_buttons.append(row)
    duration_buttons.append(back_row)
    return duration_buttons


def duration_display_config_text(panel_code: int | str, duration: int, button_obj) -> str:
    current_text = getattr(button_obj, "button_text", None) or build_default_duration_button_text(duration, "buy")
    current_style = STYLE_LABELS.get(getattr(button_obj, "button_style", None), "پیش‌فرض (بدون رنگ)")
    if getattr(button_obj, "button_style", None) == "":
        current_style = "بدون رنگ"
    current_icon = getattr(button_obj, "button_icon", None) or "ندارد"
    return (
        f"🎨 **تنظیم دکمه مدت — پنل `{panel_code}` — {duration} روز**\n\n"
        f"📝 متن: {current_text}\n"
        f"🎨 رنگ: {current_style}\n"
        f"🖼 آیکون: {current_icon}\n\n"
        "این تنظیم در خرید، تمدید و تمدید خودکار (حالت زمان اول) اعمال می‌شود.\n"
        "یکی از گزینه‌های زیر را انتخاب کنید:"
    )


def create_duration_display_config_submenu(panel_code: int | str, duration: int) -> list:
    return [
        [Button.inline("✏️ متن دکمه", data=f"duration_btn_edit_text:{panel_code}:{duration}")],
        [
            Button.inline("آبی", data=f"duration_btn_color:{panel_code}:{duration}:primary"),
            Button.inline("سبز", data=f"duration_btn_color:{panel_code}:{duration}:success"),
            Button.inline("قرمز", data=f"duration_btn_color:{panel_code}:{duration}:danger"),
            Button.inline("—", data=f"duration_btn_color:{panel_code}:{duration}:none"),
        ],
        [Button.inline("🖼 آیکون ایموجی پریمیوم", data=f"duration_btn_icon:{panel_code}:{duration}")],
        [Button.inline("🧹 حذف آیکون", data=f"duration_btn_icon_clear:{panel_code}:{duration}")],
        [Button.inline("♻️ ریست تنظیمات", data=f"duration_btn_display_reset:{panel_code}:{duration}")],
        [Button.inline("🔙 بازگشت", data=f"ManageDurationButtons_{panel_code}")],
    ]
