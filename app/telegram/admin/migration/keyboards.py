"""Keyboard builders for admin migration."""

from telethon import Button

from app.services.migration.registry import ADAPTERS
from app.telegram.admin.migration import states


def source_menu_buttons() -> list:
    rows = [
        [Button.inline(adapter.display_name, data=f"{states.MIGRATION_SOURCE_PREFIX}{slug}")]
        for slug, adapter in ADAPTERS.items()
    ]
    rows.append([Button.inline("🔙 بازگشت به پنل", data="back_to_admin_panel")])
    return rows


def confirm_buttons() -> list:
    return [
        [Button.inline("✅ تایید و شروع وارد کردن", data=states.MIGRATION_CONFIRM_CALLBACK)],
        [Button.inline("❌ لغو", data=states.MIGRATION_CANCEL_CALLBACK)],
    ]


def back_buttons() -> list:
    return [[Button.inline("🔙 بازگشت به پنل", data="back_to_admin_panel")]]
