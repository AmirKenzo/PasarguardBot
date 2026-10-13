"""Keyboard builders for admin backup."""

from telethon import Button


def menu_buttons(interval_hours: int) -> list:
    interval_label = "⏸ خودکار خاموش" if interval_hours <= 0 else f"⏱ فاصله: هر {interval_hours} ساعت"
    return [
        [Button.inline("🚀 بکاپ همین الان", data="backup_run_now")],
        [Button.inline(f"⚙️ تنظیم فاصله ({interval_label})", data="backup_set_interval")],
        [Button.inline("🔙 بازگشت به پنل", data="back_to_admin_panel")],
    ]


def interval_prompt_buttons() -> list:
    return [
        [Button.inline("🔙 بازگشت", data="backup_menu")],
    ]
