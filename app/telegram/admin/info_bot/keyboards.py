"""Inline keyboards for admin stats/info bot panel."""

from telethon import Button

from app.telegram.admin.info_bot import states


def inline_btn(label: str, data: str):
    return Button.inline(label, data=data)


def period_btn(key: str, active: str, section: str) -> object:
    label = states.REVENUE_PERIODS[key]
    if key == active:
        label = f"• {label}"
    return inline_btn(label, f"{states.STATS_PREFIX}{section}:{key}")


def period_buttons(section: str, active: str) -> list:
    return [
        [
            period_btn("1d", active, section),
            period_btn("2d", active, section),
            period_btn("3d", active, section),
            period_btn("4d", active, section),
        ],
        [period_btn("5d", active, section), period_btn("6d", active, section), period_btn("7d", active, section)],
        [
            period_btn("1m", active, section),
            period_btn("2m", active, section),
            period_btn("3m", active, section),
            period_btn("all", active, section),
        ],
        [inline_btn("🔙 بازگشت", f"{states.STATS_PREFIX}main")],
    ]


def main_menu_buttons() -> list:
    prefix = states.STATS_PREFIX
    return [
        [
            inline_btn("💰 گزارش مالی", f"{prefix}revenue:1d"),
            inline_btn("🏆 مشتریان برتر", f"{prefix}top:today"),
        ],
        [
            inline_btn("📡 سرویس‌ها", f"{prefix}services:1d"),
        ],
        [inline_btn("🧪 سیستم", f"{prefix}system")],
        [inline_btn("🔄 بروزرسانی", f"{prefix}refresh")],
    ]


def top_buttons(view: str) -> list:
    prefix = states.STATS_PREFIX
    tabs = [("today", "⭐ امروز"), ("spend", "💰 مبلغ"), ("recharge", "🔢 شارژ"), ("config", "📦 کانفیگ")]
    return [
        [inline_btn(f"{'• ' if k == view else ''}{t}", f"{prefix}top:{k}") for k, t in tabs[:2]],
        [inline_btn(f"{'• ' if k == view else ''}{t}", f"{prefix}top:{k}") for k, t in tabs[2:]],
        [inline_btn("🔙 بازگشت", f"{prefix}main")],
    ]


def system_buttons() -> list:
    prefix = states.STATS_PREFIX
    return [
        [
            inline_btn("🔄 بروزرسانی", f"{prefix}system:refresh"),
            inline_btn("🔙 بازگشت", f"{prefix}main"),
        ],
    ]
