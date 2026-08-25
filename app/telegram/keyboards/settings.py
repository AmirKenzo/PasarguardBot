"""Admin settings menu buttons."""

from dataclasses import dataclass

from telethon.tl import types

from app.logger import get_logger
from app.services.telegram.rich_message import rt as _rt, rt_bold as _rt_bold
from app.telegram.user.start.helpers import is_start_reaction_enabled

from .common import build_telegram_button_style, styled_callback_button

logger = get_logger(__name__)


def sts_txt(value: bool) -> str:
    """Return ON/OFF emoji text for boolean values."""
    return "✅" if value else "❌"


@dataclass(frozen=True)
class SettingsMenuItem:
    label: str
    attr: str
    default: bool = False
    wide: bool = False


@dataclass(frozen=True)
class SettingsMenuSection:
    key: str
    title: str
    description: str
    items: tuple[SettingsMenuItem, ...]
    columns: int = 3
    separate_page: bool = True


SETTINGS_MENU_TEXT = (
    "⚙️ مرکز کنترل تنظیمات ربات\n\n"
    "برای مدیریت راحت‌تر، تنظیمات به چند بخش جدا تقسیم شده‌اند. وارد هر بخش شو، توضیح همان بخش را بخوان و فقط گزینه‌های همان قسمت را تغییر بده.\n\n"
    "🟢 سبز یعنی فعال\n"
    "🔴 قرمز یعنی غیرفعال\n\n"
    "برای شروع، یکی از بخش‌های زیر را انتخاب کن."
)

SETTINGS_MENU_SECTIONS = (
    SettingsMenuSection(
        "core",
        "⚙️ کنترل‌های اصلی ربات و فروش",
        "وضعیت کلی ربات، فروش، خرید تک‌پنل و قفل کانال از این بخش کنترل می‌شود.",
        (
            SettingsMenuItem("وضعیت ربات", "bot_mode", default=True),
            SettingsMenuItem("وضعیت فروش", "sale_mode"),
            SettingsMenuItem("خرید تک‌پنل", "single_panel_buy_mode"),
            SettingsMenuItem("قفل کانال", "channel_lock"),
            SettingsMenuItem("ری‌اکشن استارت", "start_reaction", default=True, wide=True),
        ),
        separate_page=False,
    ),
    SettingsMenuSection(
        "payments",
        "💳 پرداخت‌ها و روش‌های شارژ",
        "فعال یا غیرفعال کردن دکمه‌های کارت دستی و درگاه ارزی در منوی شارژ کیف پول.",
        (
            SettingsMenuItem("دکمه کارت دستی", "pay_mode"),
            SettingsMenuItem("دکمه درگاه ارزی", "arz_mode"),
            SettingsMenuItem("درخواست شماره برای کارت‌به‌کارت", "pay_phone_verify", default=True, wide=True),
        ),
        columns=2,
    ),
    SettingsMenuSection(
        "service_purchase",
        "🛍 خرید، تمدید و سرویس تست",
        "گزینه‌های مربوط به خرید زمان، افزایش حجم، تمدید سرویس و دریافت کانفیگ تست در این بخش قرار دارد.",
        (
            SettingsMenuItem("دکمه خرید زمان", "extension_mode"),
            SettingsMenuItem("افزایش حجم", "upg_mode"),
            SettingsMenuItem("تمدید سرویس", "tamdid_mode"),
            SettingsMenuItem("دکمه دریافت تست", "test_mode"),
            SettingsMenuItem("تایید شماره تست", "test_phone_verify", default=True, wide=True),
            SettingsMenuItem("پرداخت مستقیم خرید", "direct_pay_purchase_mode", wide=True),
            SettingsMenuItem("پرداخت مستقیم تمدید", "direct_pay_renew_mode", wide=True),
        ),
    ),
    SettingsMenuSection(
        "reseller_sales",
        "🏢 فروش نمایندگی پنل",
        "فعال‌سازی فروش نمایندگی و مدیریت حداقل موجودی کیف پول برای نمایندگان.",
        (SettingsMenuItem("فروش نمایندگی", "reseller_sale_mode"),),
        columns=1,
    ),
    SettingsMenuSection(
        "home_menu",
        "🏠 دکمه‌های منوی اصلی",
        "نمایش یا مخفی کردن دکمه‌های اصلی صفحه هوم. این بخش جدا از ابزارهای صفحه سرویس است و پیش‌فرض همه گزینه‌ها روشن است.",
        (
            SettingsMenuItem("پروفایل من", "profile_mode", default=True),
            SettingsMenuItem("راهنما", "help_mode", default=True),
            SettingsMenuItem("پشتیبانی", "support_mode", default=True),
            SettingsMenuItem("تنظیمات پیشرفته", "advanced_settings_mode", default=True, wide=True),
        ),
        columns=2,
    ),
    SettingsMenuSection(
        "service_tools",
        "🔗 دکمه‌ها و ابزارهای صفحه سرویس",
        "این بخش تعیین می‌کند کاربر داخل صفحه سرویس چه ابزارهایی مثل QR، لینک‌ها، کلاینت‌ها و انتقال کانفیگ ببیند.",
        (
            SettingsMenuItem("دریافت QR Code", "qr_mode"),
            SettingsMenuItem("تغییر ساب", "sub_mode"),
            SettingsMenuItem("لینک‌های دیگر", "other_links_mode"),
            SettingsMenuItem("کلاینت‌ها", "client_list_mode"),
            SettingsMenuItem("نمودار مصرف", "usage_chart_mode"),
            SettingsMenuItem("تغییر لینک", "change_link_mode"),
            SettingsMenuItem("کپی لینک", "copy_link_mode"),
            SettingsMenuItem("انتقال کانفیگ", "transfer_config_mode"),
            SettingsMenuItem("اطلاعات بیشتر", "info_mode"),
            SettingsMenuItem("حذف سرویس غیرفعال", "del_service_mode", wide=True),
        ),
        columns=2,
    ),
)


def _settings_header(title: str):
    return styled_callback_button(
        f"━━ {title} ━━",
        b"no_action",
        build_telegram_button_style("primary", None),
    )


def _settings_state_style(enabled: bool):
    return build_telegram_button_style("success" if enabled else "danger", None)


def get_settings_menu_section(section_key: str | None) -> SettingsMenuSection | None:
    if not section_key:
        return None
    return next((section for section in SETTINGS_MENU_SECTIONS if section.key == section_key), None)


def get_settings_menu_item(attr: str | None) -> SettingsMenuItem | None:
    if not attr:
        return None
    for section in SETTINGS_MENU_SECTIONS:
        for item in section.items:
            if item.attr == attr:
                return item
    return None


def get_settings_section_key_for_attr(attr: str | None) -> str | None:
    if not attr:
        return None
    for section in SETTINGS_MENU_SECTIONS:
        if any(item.attr == attr for item in section.items):
            return section.key if section.separate_page else None
    return None


def get_settings_menu_text(section_key: str | None = None) -> str:
    section = get_settings_menu_section(section_key)
    if section is None:
        return SETTINGS_MENU_TEXT

    return (
        f"{section.title}\n\n"
        f"{section.description}\n\n"
        "🟢 سبز یعنی فعال\n"
        "🔴 قرمز یعنی غیرفعال\n\n"
        "برای تغییر هر گزینه، روی همان دکمه بزن."
    )


def _settings_section_button(section: SettingsMenuSection):
    return styled_callback_button(
        section.title,
        f"settings_menu:{section.key}",
        build_telegram_button_style("primary", None),
    )


def _settings_home_button():
    return styled_callback_button("🏠 فهرست بخش‌ها", b"settings_menu:home", build_telegram_button_style("primary", None))


def _settings_nav_buttons(section_key: str) -> list:
    sections = [section for section in SETTINGS_MENU_SECTIONS if section.separate_page]
    current_index = next((index for index, section in enumerate(sections) if section.key == section_key), None)
    if current_index is None:
        return [_settings_home_button()]

    row = []
    if current_index > 0:
        row.append(
            styled_callback_button(
                "⬅️ بخش قبلی",
                f"settings_menu:{sections[current_index - 1].key}",
                build_telegram_button_style("primary", None),
            )
        )

    row.append(_settings_home_button())

    if current_index < len(sections) - 1:
        row.append(
            styled_callback_button(
                "بخش بعدی ➡️",
                f"settings_menu:{sections[current_index + 1].key}",
                build_telegram_button_style("primary", None),
            )
        )

    return row


async def _settings_toggle_button(settings, item: SettingsMenuItem):
    if item.attr == "start_reaction":
        value = await is_start_reaction_enabled()
    else:
        value = bool(getattr(settings, item.attr, item.default))
    return styled_callback_button(
        item.label,
        f"settings.{item.attr}",
        _settings_state_style(value),
    )


async def _append_settings_section(rows: list[list], settings, section: SettingsMenuSection) -> None:
    rows.append([_settings_header(section.title)])
    current_row = []
    columns = max(1, section.columns)

    for item in section.items:
        button = await _settings_toggle_button(settings, item)
        if item.wide:
            if current_row:
                rows.append(current_row)
                current_row = []
            rows.append([button])
            continue

        current_row.append(button)
        if len(current_row) == columns:
            rows.append(current_row)
            current_row = []

    if current_row:
        rows.append(current_row)


async def create_buttons_settings(settings, section_key: str | None = None):
    logger.debug("Creating settings buttons")

    buttons: list[list] = []
    section = get_settings_menu_section(section_key)
    if section is not None:
        await _append_settings_section(buttons, settings, section)
        buttons.append(_settings_nav_buttons(section.key))
        return buttons

    for section in SETTINGS_MENU_SECTIONS:
        if section.separate_page:
            buttons.append([_settings_section_button(section)])
            continue

        await _append_settings_section(buttons, settings, section)

    return buttons


async def _settings_rich_toggle_button(settings, item: SettingsMenuItem) -> types.PageButton:
    if item.attr == "start_reaction":
        value = await is_start_reaction_enabled()
    else:
        value = bool(getattr(settings, item.attr, item.default))
    return types.PageButton(
        text=_rt(item.label),
        type=types.InlineButtonTypeCallback(data=f"settings.{item.attr}".encode()),
        style=types.RichButtonStyle(bg_success=True) if value else types.RichButtonStyle(bg_danger=True),
    )


async def _settings_rich_section_rows(settings, section: SettingsMenuSection) -> list[types.PageBlockButtonRow]:
    """Native Bot API 10.3 'Button Revolution' toggle grid, replacing the plain inline keyboard."""
    rows: list[types.PageBlockButtonRow] = []
    current_row: list[types.PageButton] = []
    columns = max(1, section.columns)

    for item in section.items:
        button = await _settings_rich_toggle_button(settings, item)
        if item.wide:
            if current_row:
                rows.append(types.PageBlockButtonRow(buttons=current_row))
                current_row = []
            rows.append(types.PageBlockButtonRow(buttons=[button]))
            continue

        current_row.append(button)
        if len(current_row) == columns:
            rows.append(types.PageBlockButtonRow(buttons=current_row))
            current_row = []

    if current_row:
        rows.append(types.PageBlockButtonRow(buttons=current_row))
    return rows


def _settings_rich_home_button() -> types.PageButton:
    return types.PageButton(
        text=_rt("🏠 فهرست بخش‌ها"),
        type=types.InlineButtonTypeCallback(data=b"settings_menu:home"),
        style=types.RichButtonStyle(bg_primary=True),
    )


def _settings_rich_nav_button_rows(section_key: str) -> list[types.PageBlockButtonRow]:
    sections = [section for section in SETTINGS_MENU_SECTIONS if section.separate_page]
    current_index = next((index for index, section in enumerate(sections) if section.key == section_key), None)
    if current_index is None:
        return [types.PageBlockButtonRow(buttons=[_settings_rich_home_button()])]

    row = []
    if current_index > 0:
        row.append(
            types.PageButton(
                text=_rt("⬅️ بخش قبلی"),
                type=types.InlineButtonTypeCallback(data=f"settings_menu:{sections[current_index - 1].key}".encode()),
                style=types.RichButtonStyle(bg_primary=True),
            )
        )

    row.append(_settings_rich_home_button())

    if current_index < len(sections) - 1:
        row.append(
            types.PageButton(
                text=_rt("بخش بعدی ➡️"),
                type=types.InlineButtonTypeCallback(data=f"settings_menu:{sections[current_index + 1].key}".encode()),
                style=types.RichButtonStyle(bg_primary=True),
            )
        )

    return [types.PageBlockButtonRow(buttons=row)]


async def settings_menu_rich_blocks(settings, section_key: str | None = None) -> list:
    """Native Bot API 10.3 rich message blocks for the ⚙️ settings panel (toggle buttons in-body)."""
    section = get_settings_menu_section(section_key)
    status_line = "🟢 سبز یعنی فعال   ·   🔴 قرمز یعنی غیرفعال"

    if section is not None:
        blocks: list = [
            types.PageBlockParagraph(_rt_bold(section.title)),
            types.PageBlockParagraph(_rt(section.description)),
            types.PageBlockParagraph(_rt(f"{status_line}\nبرای تغییر هر گزینه، روی همان دکمه بزن.")),
            types.PageBlockDivider(),
        ]
        blocks.extend(await _settings_rich_section_rows(settings, section))
        blocks.append(types.PageBlockDivider())
        blocks.extend(_settings_rich_nav_button_rows(section.key))
        return blocks

    blocks = [
        types.PageBlockParagraph(_rt_bold("⚙️ مرکز کنترل تنظیمات ربات")),
        types.PageBlockParagraph(
            _rt(
                "برای مدیریت راحت‌تر، تنظیمات به چند بخش جدا تقسیم شده‌اند. "
                "وارد هر بخش شو، توضیح همان بخش را بخوان و فقط گزینه‌های همان قسمت را تغییر بده."
            )
        ),
        types.PageBlockParagraph(_rt(status_line)),
        types.PageBlockDivider(),
    ]

    for menu_section in SETTINGS_MENU_SECTIONS:
        if menu_section.separate_page:
            blocks.append(
                types.PageBlockButtonRow(
                    buttons=[
                        types.PageButton(
                            text=_rt(menu_section.title),
                            type=types.InlineButtonTypeCallback(data=f"settings_menu:{menu_section.key}".encode()),
                            style=types.RichButtonStyle(bg_primary=True),
                        )
                    ]
                )
            )
            continue

        blocks.append(types.PageBlockParagraph(_rt_bold(menu_section.title)))
        blocks.extend(await _settings_rich_section_rows(settings, menu_section))
        blocks.append(types.PageBlockDivider())

    return blocks
