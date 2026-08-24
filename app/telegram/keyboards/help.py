"""Help menu and help-button management keyboards."""

from telethon import Button

from app.db.crud.help_buttons import HelpButtonCRUD, HelpDownloadAppCRUD
from config import ADMIN_ID, TUTORIAL_HELP_LINKS

from .common import _build_help_button_telegram, _help_button_style, styled_callback_button


async def get_help_buttons(user_id: int | None = None):
    """Help buttons from DB ordered by button_number. Consecutive numbers = same row; gap = new row."""
    help_crud = HelpButtonCRUD()
    all_buttons = await help_crud.get_all_buttons()

    rows = []
    current_row = []
    prev_num = None
    for btn in all_buttons:
        b = _build_help_button_telegram(btn)
        if b is None:
            continue
        if prev_num is not None and btn.button_number != prev_num + 1:
            if current_row:
                rows.append(current_row)
            current_row = []
        current_row.append(b)
        prev_num = btn.button_number
    if current_row:
        rows.append(current_row)

    if not rows:
        try:
            db_apps = await HelpDownloadAppCRUD().get_all()
            if not db_apps:
                rows = [
                    [Button.inline("👇 دانلود برنامه‌ها از دکمه‌های زیر 👇", data="no_action")],
                    [
                        Button.inline("Hiddify", data="Download_hiddifyapp"),
                        Button.inline("V2rayNG", data="Download_v2rayng"),
                    ],
                    [
                        Button.inline("V2rayN", data="Download_v2rayn"),
                        Button.inline("Nekoray (Throne)", data="Download_Throne"),
                    ],
                    [Button.inline("Streisand", data="IOS_streisand"), Button.inline("FairVPN", data="IOS_fairvpn")],
                    [Button.inline("Happ Android", data="Download_happandroid")],
                ]
        except Exception:
            rows = [
                [Button.inline("👇 دانلود برنامه‌ها از دکمه‌های زیر 👇", data="no_action")],
                [
                    Button.inline("Hiddify", data="Download_hiddifyapp"),
                    Button.inline("V2rayNG", data="Download_v2rayng"),
                ],
                [
                    Button.inline("V2rayN", data="Download_v2rayn"),
                    Button.inline("Nekoray (Throne)", data="Download_Throne"),
                ],
                [Button.inline("Streisand", data="IOS_streisand"), Button.inline("FairVPN", data="IOS_fairvpn")],
                [Button.inline("Happ Android", data="Download_happandroid")],
            ]
    if user_id and user_id in ADMIN_ID:
        rows.append([Button.inline("⚙️ تنظیمات راهنما", data="help_settings_admin")])
    return rows


inline_buttons = [
    [Button.url("🔰 لیست تمام آموزش ها", url=TUTORIAL_HELP_LINKS)],
    [Button.inline("-------------", data="no_action")],
    [Button.inline("Hiddify", data="Download_hiddifyapp"), Button.inline("V2rayNG", data="Download_v2rayng")],
    [Button.inline("V2rayN", data="Download_v2rayn"), Button.inline("Nekoray (Throne)", data="Download_Throne")],
    [Button.inline("Streisand", data="IOS_streisand"), Button.inline("FairVPN", data="IOS_fairvpn")],
    [Button.inline("Happ Android", data="Download_happandroid")],
]


def create_help_button_submenu(button_num: int) -> list:
    """Submenu for one help link button: text, link, color, icon, delete. Clear and compact."""
    return [
        [
            Button.inline("✏️ متن", data=f"help_btn_edit_text:{button_num}"),
            Button.inline("🔗 لینک", data=f"help_btn_edit_link:{button_num}"),
        ],
        [
            Button.inline("آبی", data=f"help_btn_color:{button_num}:primary"),
            Button.inline("سبز", data=f"help_btn_color:{button_num}:success"),
            Button.inline("قرمز", data=f"help_btn_color:{button_num}:danger"),
            Button.inline("—", data=f"help_btn_color:{button_num}:none"),
        ],
        [Button.inline("🖼 آیکون", data=f"help_btn_icon:{button_num}")],
        [Button.inline("🧹 حذف آیکون", data=f"help_btn_icon_clear:{button_num}")],
        [Button.inline("🗑 حذف دکمه", data=f"help_btn_delete:{button_num}")],
        [Button.inline("🔙 بازگشت", data="back_to_help_config")],
    ]


async def create_help_buttons_config_ui(back_data: str = "backTOhelp"):
    """Config UI: only existing link buttons (no callback_key) + Add button. No fixed empty slots."""
    help_crud = HelpButtonCRUD()
    all_buttons = await help_crud.get_all_buttons()
    link_buttons = [b for b in all_buttons if getattr(b, "callback_key", None) is None]
    link_buttons.sort(key=lambda b: b.button_number)

    buttons = []
    for btn in link_buttons:
        num = btn.button_number
        if (btn.button_text or "").strip() and (btn.button_url or "").strip():
            short = (btn.button_text or "").strip()
            if len(short) > 12:
                short = short[:10] + "…"
            label = f"{num}. {short}"
            style_obj = _help_button_style(btn.button_style, btn.button_icon)
            data = f"help_btn_config:{num}".encode()
            if style_obj:
                buttons.append([styled_callback_button(label, data, style_obj)])
            else:
                buttons.append([Button.inline(label, data=f"help_btn_config:{num}")])
        else:
            buttons.append(
                [
                    Button.inline(f"{num}. خالی", data=f"help_btn_config:{num}"),
                    Button.inline("🗑 حذف", data=f"help_btn_delete:{num}"),
                ]
            )

    buttons.append([Button.inline("➕ افزودن دکمه لینک", data="help_btn_add")])
    buttons.append([Button.inline("🔙 بازگشت", data=back_data)])
    return buttons


async def create_help_reorder_ui(back_data: str = "back_to_help_settings"):
    """Reorder: click a button then send new position (1 to N) in chat. Max 2 per row in help."""
    help_crud = HelpButtonCRUD()
    all_buttons = await help_crud.get_all_buttons()
    lines = []
    rows = []
    for btn in all_buttons:
        num = btn.button_number
        label = (btn.button_text or "").strip() or ("اپ" if getattr(btn, "callback_key", None) else "لینک")
        if len(label) > 16:
            label = label[:14] + "…"
        lines.append(f"{num}. {label}")
        rows.append([Button.inline(f"{num}. {label}", data=f"help_btn_reorder_set:{btn.id}")])
    intro = (
        "📐 **ترتیب دکمه‌های راهنما**\n\n"
        "روی دکمه بزنید، بعد **هر عدد دلخواه** بفرستید (همون عدد = button_number آن رکورد)، مثلاً ۱، ۱۷، ۱۰۰۰.\n"
        "عددهای **پشت‌سرهم** → کنار هم؛ **فاصله** بین عددها → ردیف جدید.\n\n"
    )
    text = intro + ("\n".join(lines) if lines else "هیچ دکمه‌ای ثبت نشده.")
    if rows:
        rows.append([Button.inline("🔙 بازگشت", data=back_data)])
    else:
        rows = [[Button.inline("🔙 بازگشت", data=back_data)]]
    return text, rows


inline_back = [[Button.inline("بازگشت", data="backTOhelp")]]
