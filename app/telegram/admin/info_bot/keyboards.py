"""Inline keyboards for admin stats/info bot panel."""

from telethon import Button
from telethon.tl.types import (
    KeyboardButtonCallback,
    KeyboardButtonCopy,
    KeyboardButtonRow,
    KeyboardButtonStyle,
    ReplyInlineMarkup,
)

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


def services_buttons(period: str) -> list:
    rows = period_buttons("services", period)
    rows.insert(0, [inline_btn("🔄 بروزرسانی", f"{states.STATS_PREFIX}services:{period}:refresh")])
    return rows


def system_buttons(settings_payload: dict) -> ReplyInlineMarkup:
    prefix = states.STATS_PREFIX
    arz_usd = settings_payload.get("arz_usd", 0)
    arz_trx = settings_payload.get("arz_trx", 0)
    arz_ton = settings_payload.get("arz_ton", 0)
    return ReplyInlineMarkup(
        rows=[
            KeyboardButtonRow(
                [
                    KeyboardButtonCopy(
                        text=f"USDT {arz_usd:,} IRT",
                        copy_text=f"USDT {arz_usd:,}",
                        style=KeyboardButtonStyle(icon=5280963835790894176),
                    ),
                    KeyboardButtonCopy(
                        text=f"TRX {arz_trx:,} IRT",
                        copy_text=f"TRX {arz_trx:,}",
                        style=KeyboardButtonStyle(icon=5292038911474804405),
                    ),
                ]
            ),
            KeyboardButtonRow(
                [
                    KeyboardButtonCopy(
                        text=f"GRAM {arz_ton:,} IRT",
                        copy_text=f"GRAM {arz_ton:,}",
                        style=KeyboardButtonStyle(icon=5305626186544599263),
                    ),
                ]
            ),
            KeyboardButtonRow(
                [
                    KeyboardButtonCallback(
                        text="🔄 بروزرسانی",
                        data=f"{prefix}system:refresh".encode(),
                        requires_password=True,
                    ),
                    KeyboardButtonCallback(
                        text="🔙 بازگشت",
                        data=f"{prefix}main".encode(),
                        requires_password=True,
                    ),
                ]
            ),
        ]
    )
