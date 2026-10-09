"""Admin screens for a panel's invoice locations and node prefixes.

Callback data here only ever carries the panel code and a fixed token or a list
index — never admin-written text. Prefixes and locations often contain flag
emoji (several bytes each), and a single button over Telegram's 64-byte limit
makes the whole screen fail to send, leaving no way back in to fix it.
"""

from __future__ import annotations

from telethon import Button

from app.services.panels.locations import (
    LOCATIONS_MODE_LABELS,
    panel_locations_mode,
    panel_manual_locations,
)
from app.services.panels.settings import (
    LOCATION_MAX_LENGTH,
    LOCATIONS_MAX_ITEMS,
    LOCATIONS_MODE_AUTO,
    LOCATIONS_MODE_HIDDEN,
    LOCATIONS_MODE_MANUAL,
    panel_node_prefixes,
    panel_show_prefixes_in_locations,
)

STEP_WAITING_LOCATIONS = "waiting_panel_locations"
LOCATIONS_PANEL_KEY = "panel_locations_panel_code"

DEFAULT_NODE_PREFIXES: tuple[str, ...] = ("LT -", "HYB -", "UL -")

_MODE_BUTTON_LABELS: dict[str, str] = {
    LOCATIONS_MODE_AUTO: "🛰 خودکار",
    LOCATIONS_MODE_MANUAL: "✍️ دستی",
    LOCATIONS_MODE_HIDDEN: "🙈 مخفی",
}


def build_locations_view(panel) -> tuple[str, list]:
    code = panel.code
    mode = panel_locations_mode(panel)
    manual = panel_manual_locations(panel)
    manual_text = "\n".join(f"▫️ {item}" for item in manual) if manual else "— خالی —"
    text = (
        f"**📍 لوکیشن‌های فاکتور — پنل {panel.name}**\n\n"
        f"**حالت فعلی:** {LOCATIONS_MODE_LABELS[mode]}\n\n"
        f"**لیست دستی:**\n{manual_text}\n\n"
        "🛰 **خودکار:** نودهای همین پنل (با فیلتر پیشوند نوع پلن) نمایش داده می‌شوند.\n"
        "✍️ **دستی:** لیست بالا نمایش داده می‌شود؛ اگر خالی باشد، نودها نمایش داده می‌شوند.\n"
        "🙈 **مخفی:** خط لوکیشن‌ها روی فاکتور این پنل نمایش داده نمی‌شود."
    )
    mode_row = [
        Button.inline(
            f"{'✅ ' if key == mode else ''}{label}",
            data=f"panel_locations_mode:{code}:{key}",
        )
        for key, label in _MODE_BUTTON_LABELS.items()
    ]
    buttons = [mode_row, [Button.inline("✏️ ویرایش لیست دستی", data=f"panel_locations_edit:{code}")]]
    if manual:
        buttons.append([Button.inline("🧹 پاک کردن لیست دستی", data=f"panel_locations_clear:{code}")])
    buttons.append([Button.inline("🔙 بازگشت", data=f"panel_info:{code}")])
    return text, buttons


def locations_edit_prompt(panel) -> tuple[str, list]:
    text = (
        f"**✏️ لیست لوکیشن‌های پنل {panel.name}**\n\n"
        "هر لوکیشن را در یک خط جدا بفرستید (می‌توانید پرچم هم بگذارید).\n"
        f"حداکثر {LOCATIONS_MAX_ITEMS} مورد و هر کدام تا {LOCATION_MAX_LENGTH} کاراکتر.\n\n"
        "**مثال:**\n🇩🇪 آلمان\n🇫🇮 فنلاند\n🇳🇱 هلند\n\n"
        "ارسال لیست جدید، جایگزین لیست فعلی می‌شود."
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
        "💡 برای نوشتن اسم و پرچم دلخواه لوکیشن‌ها از بخش «📍 لوکیشن‌های فاکتور» استفاده کنید."
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
