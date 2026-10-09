"""Admin screens for a panel's invoice locations and node prefixes.

Callback data here only ever carries the panel code and a fixed token or a list
index — never admin-written text. Prefixes and locations often contain flag
emoji (several bytes each), and a single button over Telegram's 64-byte limit
makes the whole screen fail to send, leaving no way back in to fix it.

For the same reason the screen shows the stored locations as escaped plain text
(HTML mode, trimmed): the admin's own markdown never decides whether the screen
can be drawn. The "preview" button sends the text as the invoice will show it.
"""

from __future__ import annotations

import html

from telethon import Button

from app.services.panels.locations import (
    LOCATIONS_MODE_LABELS,
    LOCATIONS_TEXT_MAX_LENGTH,
    get_manual_locations_text,
    panel_locations_mode,
    plain_location,
)
from app.services.panels.settings import (
    LOCATIONS_MODE_AUTO,
    LOCATIONS_MODE_HIDDEN,
    LOCATIONS_MODE_MANUAL,
    panel_node_prefixes,
    panel_show_prefixes_in_locations,
)

STEP_WAITING_LOCATIONS = "waiting_panel_locations"
LOCATIONS_PANEL_KEY = "panel_locations_panel_code"
_PREVIEW_CHARS = 600

DEFAULT_NODE_PREFIXES: tuple[str, ...] = ("LT -", "HYB -", "UL -")

_MODE_BUTTON_LABELS: dict[str, str] = {
    LOCATIONS_MODE_AUTO: "🛰 خودکار",
    LOCATIONS_MODE_MANUAL: "✍️ دستی",
    LOCATIONS_MODE_HIDDEN: "🙈 مخفی",
}


async def build_locations_view(panel) -> tuple[str, list]:
    """Screen text (HTML) and buttons for a panel's invoice locations."""
    code = panel.code
    mode = panel_locations_mode(panel)
    manual = (await get_manual_locations_text(panel)).strip()
    if manual:
        preview = plain_location(manual)
        if len(preview) > _PREVIEW_CHARS:
            preview = f"{preview[:_PREVIEW_CHARS]}…"
        manual_html = f"<blockquote expandable>{html.escape(preview)}</blockquote>"
    else:
        manual_html = "— ثبت نشده —"
    text = (
        f"<b>📍 لوکیشن‌های فاکتور — پنل {html.escape(panel.name)}</b>\n\n"
        f"<b>حالت فعلی:</b> {LOCATIONS_MODE_LABELS[mode]}\n\n"
        f"<b>متن دستی:</b>\n{manual_html}\n\n"
        "🛰 <b>خودکار:</b> نودهای همین پنل (با فیلتر پیشوند نوع پلن) نمایش داده می‌شوند.\n"
        "✍️ <b>دستی:</b> متن شما دقیقاً همان‌طور که فرستاده‌اید جای بخش لوکیشن فاکتور می‌نشیند "
        "(عنوان هم با خودتان است). اگر متنی ثبت نشده باشد، نودها نمایش داده می‌شوند.\n"
        "🙈 <b>مخفی:</b> بخش لوکیشن‌ها روی فاکتور این پنل نمایش داده نمی‌شود."
    )
    mode_row = [
        Button.inline(
            f"{'✅ ' if key == mode else ''}{label}",
            data=f"panel_locations_mode:{code}:{key}",
        )
        for key, label in _MODE_BUTTON_LABELS.items()
    ]
    buttons = [mode_row, [Button.inline("✏️ ثبت / ویرایش متن دستی", data=f"panel_locations_edit:{code}")]]
    if manual:
        buttons.append(
            [
                Button.inline("👁 پیش‌نمایش", data=f"panel_locations_preview:{code}"),
                Button.inline("🧹 پاک کردن متن", data=f"panel_locations_clear:{code}"),
            ]
        )
    buttons.append([Button.inline("🔙 بازگشت", data=f"panel_info:{code}")])
    return text, buttons


def locations_edit_prompt(panel) -> tuple[str, list]:
    text = (
        f"**✏️ متن لوکیشن‌های پنل {panel.name}**\n\n"
        "متن را همان‌طور که می‌خواهید روی فاکتور دیده شود بفرستید؛ با عنوان، چینش، "
        "بولد و ایموجی پریمیوم. دقیقاً همین متن جای بخش لوکیشن فاکتور می‌نشیند.\n"
        f"حداکثر {LOCATIONS_TEXT_MAX_LENGTH} کاراکتر.\n\n"
        "**مثال:**\n🌍 لوکیشن‌ها:\n🇩🇪 آلمان ⌁ 🇫🇮 فنلاند ⌁ 🇳🇱 هلند\n\n"
        "متن جدید جایگزین متن فعلی می‌شود."
    )
    return text, [[Button.inline("❌ انصراف", data=f"panel_locations:{panel.code}")]]


def node_prefix_options(panel) -> list[str]:
    """Defaults first, then the panel's custom prefixes, in a stable order."""
    options = list(DEFAULT_NODE_PREFIXES)
    options.extend(prefix for prefix in panel_node_prefixes(panel) if prefix not in options)
    return options


def build_node_prefixes_view(panel) -> tuple[str, list]:
    code = panel.code
    current = panel_node_prefixes(panel)
    buttons = [
        [
            Button.inline(
                f"{'✅' if prefix in current else '☐'} {prefix}",
                data=f"panel_node_prefix_toggle:{code}:{index}",
            )
        ]
        for index, prefix in enumerate(node_prefix_options(panel))
    ]
    buttons.append([Button.inline("➕ افزودن پیشوند سفارشی", data=f"panel_node_prefix_add_custom:{code}")])
    show_prefixes = panel_show_prefixes_in_locations(panel)
    buttons.append(
        [
            Button.inline(
                "✅ نمایش پیشوندها" if show_prefixes else "❌ مخفی کردن پیشوندها",
                data=f"panel_toggle_show_prefixes:{code}",
            )
        ]
    )
    buttons.append([Button.inline("🔙 بازگشت", data=f"panel_info:{code}")])

    prefix_list = ", ".join(current) if current else "هیچ پیشوندی انتخاب نشده"
    text = (
        f"**🌐 مدیریت پیشوندهای نود - پنل {panel.name}**\n\n"
        f"**پیشوندهای انتخاب شده:**\n`{prefix_list}`\n\n"
        f"**نمایش پیشوندها در لوکیشن‌ها:** {'✅ فعال' if show_prefixes else '❌ غیرفعال'}\n\n"
        "**راهنما:**\n"
        "• **LT -** برای نودهای حجمی\n"
        "• **HYB -** برای نودهای ترکیبی (حجمی + نامحدود)\n"
        "• **UL -** برای نودهای نامحدود\n\n"
        "برای انتخاب/لغو انتخاب هر پیشوند روی آن کلیک کنید.\n"
        "💡 برای نوشتن متن دلخواه لوکیشن‌ها از بخش «📍 لوکیشن‌های فاکتور» استفاده کنید."
    )
    return text, buttons


def resolve_prefix_token(panel, token: str) -> str | None:
    """Map a toggle button's token back to its prefix.

    Current buttons carry a list index; buttons drawn before this change carried
    the prefix itself, so anything that is not a valid index is taken literally.
    """
    options = node_prefix_options(panel)
    if token.isdigit() and int(token) < len(options):
        return options[int(token)]
    return token or None
