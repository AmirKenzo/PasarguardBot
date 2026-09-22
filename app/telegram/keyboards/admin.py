"""Admin reply/inline keyboard builders."""

from dataclasses import dataclass

from telethon import Button

from app.db.crud.user import UserCRUD
from config import WEBAPP_URL

from .common import (
    build_telegram_button_style,
    create_button,
    glass_inline_button,
    glass_text_button,
    styled_callback_button,
    styled_simple_webview_button,
    styled_webview_button,
)

DOCS_URL = "https://amirkenzo.github.io/PasarguardBot/"
# Telegram refuses a web-view button on plain http, so the entry only exists
# once the WebApp has a real address; the URL itself is built when pressed.
WEB_PANEL_READY = WEBAPP_URL.startswith("https://")

# Callback prefixes for the in-chat version of this menu.
ADMIN_MENU_PREFIX = "adminmenu:"
ADMIN_LEAF_PREFIX = "adminleaf:"


def _admin_style(name: str):
    return build_telegram_button_style(name, None)


Lock_Channels_Menu_Buttons = [
    [glass_text_button("افزودن کانال"), glass_text_button("حذف کانال")],
    [glass_text_button("لیست کانال‌ها")],
    [glass_text_button("🔙 بازگشت به پنل")],
]
# Lock Channels (🔐) Inline Menu (fully glassy)
Lock_Channels_Inline_Menu = [
    [
        glass_inline_button("➕ افزودن کانال", data="lock_add"),
        glass_inline_button("📋 لیست کانال‌ها", data="lock_list:1"),
    ],
    [glass_inline_button("🔙 بازگشت به پنل", data="back_to_panel")],
]


async def create_inline_manageuser(UserID):
    user = await UserCRUD().read_user(UserID)
    buttons = [
        [Button.inline("📂 لیست سرویس‌ها", f"MToUser_listSv:{UserID}")],
        [Button.inline("🏢 نمایندگی‌های کاربر", f"MToUser_resellers:{UserID}")],
        [
            Button.inline("🔍 جستجوی کانفیگ", f"AdminSearchConfig:{UserID}"),
            Button.inline("🗑 حذف گروهی کانفیگ", f"BulkDeleteConfigs:{UserID}"),
        ],
        [Button.inline("رفع مسدودی", f"unbansup_{UserID}"), Button.inline("مسدود سازی", f"bansup_{UserID}")],
        [Button.inline("اطلاعات کاربر", f"UserInfo:{UserID}"), Button.inline("پیام به کاربر", f"sendm_{UserID}")],
    ]
    if not user or not user.number:
        buttons.append([Button.inline("📱 تایید شماره کاربر", f"confirm_phone_{UserID}")])

    buttons.append([Button.inline("ساخت کانفیگ برای کاربر", f"CreateConfigFor:{UserID}")])
    return buttons


def build_admin_reseller_list_buttons(user_id: int, accounts) -> list:
    rows = [
        [Button.inline(f"🏢 {acc.username} · #{acc.code}", data=f"AdminReseller_view:{user_id}:{acc.code}")]
        for acc in accounts
    ]
    rows.append([Button.inline("🔙 بازگشت", data=f"BackToUserManagement:{user_id}")])
    return rows


def build_admin_reseller_account_buttons(user_id: int, account) -> list:
    code = account.code
    rows = [
        [Button.inline("🔑 نمایش رمز ورود", data=f"AdminReseller_creds:{user_id}:{code}")],
        [Button.inline("🔄 تغییر رمز عبور", data=f"AdminReseller_chpwd:{user_id}:{code}")],
    ]
    if account.status in ("paused", "admin_paused", "usage_capped"):
        if account.status != "usage_capped":
            rows.append([Button.inline("▶️ فعال‌سازی پنل", data=f"AdminReseller_resume:{user_id}:{code}")])
    elif account.status in ("active", "suspended"):
        rows.append([Button.inline("⏸ غیرفعال‌سازی پنل", data=f"AdminReseller_pause:{user_id}:{code}")])
    if account.pricing_mode == "fixed":
        rows.append([Button.inline("💎 تمدید", data=f"AdminReseller_renew:{user_id}:{code}")])
    if account.pricing_mode == "usage":
        rows.append([Button.inline("📦 محدودیت مصرف", data=f"AdminReseller_usage_cap:{user_id}:{code}")])
    rows.append([Button.inline("🗑 حذف نمایندگی", data=f"AdminReseller_delete:{user_id}:{code}")])
    rows.append([Button.inline("🔙 بازگشت به لیست", data=f"MToUser_resellers:{user_id}")])
    return rows


def build_admin_reseller_usage_cap_buttons(user_id: int, account_code: int, *, has_cap: bool) -> list:
    rows = [
        [Button.inline("✏️ تنظیم سقف (گیگ)", data=f"AdminReseller_usage_cap_set:{user_id}:{account_code}")],
    ]
    if has_cap:
        rows.append([Button.inline("🗑 حذف سقف مصرف", data=f"AdminReseller_usage_cap_clear:{user_id}:{account_code}")])
    rows.append([Button.inline("🔙 بازگشت", data=f"AdminReseller_view:{user_id}:{account_code}")])
    return rows


def build_admin_reseller_delete_confirm_buttons(user_id: int, account_code: int) -> list:
    return [
        [Button.inline("✅ بله، کامل حذف شود", data=f"AdminReseller_delete_confirm:{user_id}:{account_code}")],
        [Button.inline("❌ انصراف", data=f"AdminReseller_view:{user_id}:{account_code}")],
    ]


def build_admin_reseller_chpwd_confirm_buttons(user_id: int, account_code: int) -> list:
    return [
        [Button.inline("✅ بله، رمز عوض شود", data=f"AdminReseller_chpwd_confirm:{user_id}:{account_code}")],
        [Button.inline("❌ انصراف", data=f"AdminReseller_view:{user_id}:{account_code}")],
    ]


@dataclass(frozen=True)
class AdminSection:
    """One drawer of the admin menu.

    ``items`` are the labels the leaf handlers already match on, so grouping
    them changes where a button lives and nothing about what it does.
    """

    key: str
    label: str
    items: tuple[str, ...] = ()
    links: tuple[tuple[str, str], ...] = ()
    columns: int = 2


ADMIN_SECTIONS: tuple[AdminSection, ...] = (
    AdminSection(
        "users",
        "👥 کاربران",
        ("👤 مدیریت کاربر", "🔄 ریست دریافت تست", "📈 افزایش حجم و زمان همگانی"),
    ),
    AdminSection(
        "finance",
        "💳 مالی و پرداخت",
        ("💳 تنظیمات درگاه", "➕ افزودن موجودی", "➖ کسر موجودی", "💰 شارژ گروهی"),
    ),
    AdminSection(
        "shop",
        "🏬 فروشگاه",
        ("🗞 ساخت پلن", "🏢 پلن نمایندگی", "🎟 کدتخفیف", "🎁 سیستم دعوت دوستان"),
    ),
    AdminSection("panels", "🖥 پنل‌ها و سرورها", ("📚 منوی پنل ها",), columns=1),
    AdminSection(
        "outreach",
        "📢 کانال‌ها و پیام‌ها",
        ("📮 ارسال همگانی", "📥 فوروارد همگانی", "🔐 قفل چنل ها", "📝 مدیریت لاگ‌ها"),
    ),
    AdminSection(
        "appearance",
        "⚙️ تنظیمات و ظاهر",
        ("⚙️ تنظیمات ربات", "📝 متن‌های ربات", "⌨️ مدیریت دکمه‌های کیبورد", "🔗 لینک های آماده"),
    ),
    AdminSection(
        "tools",
        "🧰 ابزارها",
        ("📦 بکاپ ربات", "🧬 مایگریشن از ربات دیگر", "🈸 آپدیت برنامه ها"),
        links=(("📚 مستندات ربات", DOCS_URL),),
    ),
)

# Reached every day, so they stay one press away instead of inside a drawer.
ADMIN_HOME_ACTIONS: tuple[str, ...] = ("👥 آمار گیری",) + (("🖥 پنل تحت وب",) if WEB_PANEL_READY else ())

ADMIN_BACK_LABEL = "🔙 بازگشت به پنل"
ADMIN_HOME_LABEL = "🏠"

ADMIN_SECTION_BY_LABEL: dict[str, AdminSection] = {section.label: section for section in ADMIN_SECTIONS}
ADMIN_SECTION_BY_KEY: dict[str, AdminSection] = {section.key: section for section in ADMIN_SECTIONS}


def _rows(values: list, columns: int) -> list[list]:
    return [values[index : index + columns] for index in range(0, len(values), columns)]


def admin_home_rows() -> list[list[str]]:
    """Labels of the admin home keyboard, two per row."""
    rows = _rows([section.label for section in ADMIN_SECTIONS], 2)
    rows.extend(_rows(list(ADMIN_HOME_ACTIONS), 2))
    rows.append([ADMIN_HOME_LABEL])
    return rows


def admin_section_rows(section: AdminSection) -> list[list[str]]:
    rows = _rows(list(section.items), max(1, section.columns))
    rows.extend([[label] for label, _url in section.links])
    rows.append([ADMIN_BACK_LABEL])
    return rows


# Kept under its historical name: plenty of modules send this keyboard.
Panel_Admin_Buttons = [[create_button(label) for label in row] for row in admin_home_rows()]


def admin_section_keyboard(section: AdminSection) -> list:
    rows: list = [
        [create_button(label) for label in row] for row in _rows(list(section.items), max(1, section.columns))
    ]
    rows.extend([[styled_simple_webview_button(label, url)] for label, url in section.links])
    rows.append([create_button(ADMIN_BACK_LABEL)])
    return rows


def admin_home_inline() -> list:
    """The same menu drawn inside the chat, for the glassy keyboard."""
    rows = [
        [styled_callback_button(section.label, f"{ADMIN_MENU_PREFIX}{section.key}", _admin_style("primary"))]
        for section in ADMIN_SECTIONS
    ]
    paired = _rows(rows, 2)
    inline_rows = [row[0] + row[1] if len(row) == 2 else row[0] for row in paired]
    actions = [
        styled_callback_button(label, f"{ADMIN_LEAF_PREFIX}home:{index}")
        for index, label in enumerate(ADMIN_HOME_ACTIONS)
    ]
    if actions:
        inline_rows.append(actions)
    inline_rows.append([styled_callback_button(ADMIN_HOME_LABEL, f"{ADMIN_LEAF_PREFIX}home:{len(ADMIN_HOME_ACTIONS)}")])
    return inline_rows


def admin_section_inline(section: AdminSection) -> list:
    buttons = [
        styled_callback_button(label, f"{ADMIN_LEAF_PREFIX}{section.key}:{index}")
        for index, label in enumerate(section.items)
    ]
    rows = _rows(buttons, max(1, section.columns))
    rows.extend([[styled_webview_button(label, url)] for label, url in section.links])
    rows.append([styled_callback_button(ADMIN_BACK_LABEL, b"back_to_admin_panel")])
    return rows


def admin_leaf_label(key: str, index: int) -> str | None:
    """The text a press on an in-chat admin button stands for."""
    if key == "home":
        pool = (*ADMIN_HOME_ACTIONS, ADMIN_HOME_LABEL)
    else:
        section = ADMIN_SECTION_BY_KEY.get(key)
        pool = section.items if section else ()
    return pool[index] if 0 <= index < len(pool) else None


BT_takhfifList = [
    [create_button("🎛 لیست کدتخفیف"), create_button("🪄 ساخت کدتخفیف")],
    [create_button("🔙 بازگشت به پنل")],
]

panel_xui_buttons = [
    [create_button("📉 وضعیت پنل ها"), create_button("▫️ افزودن پنل جدید")],
    [create_button("🔙 بازگشت به پنل")],
]


panel_back = [[create_button("🔙 بازگشت به پنل")]]

Home_Back = [[create_button("🏠")]]
