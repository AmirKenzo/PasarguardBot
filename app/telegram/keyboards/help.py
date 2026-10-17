"""Help menu keyboards."""

from telethon import Button

from app.db.crud.help_buttons import HelpButtonCRUD, HelpDownloadAppCRUD
from app.telegram.shared.utils.miniapp import miniapp_deeplink, miniapp_ready
from config import ADMIN_ID, TUTORIAL_HELP_LINKS

from .common import _build_help_button_telegram, styled_webview_button

HELP_BUTTONS_PANEL_PATH = "/panel/help-buttons"


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
    if user_id and user_id in ADMIN_ID and miniapp_ready():
        rows.append(
            [styled_webview_button("⚙️ تنظیمات راهنما (پنل وب)", miniapp_deeplink(HELP_BUTTONS_PANEL_PATH), None)]
        )
    return rows


inline_buttons = [
    [Button.url("🔰 لیست تمام آموزش ها", url=TUTORIAL_HELP_LINKS)],
    [Button.inline("-------------", data="no_action")],
    [Button.inline("Hiddify", data="Download_hiddifyapp"), Button.inline("V2rayNG", data="Download_v2rayng")],
    [Button.inline("V2rayN", data="Download_v2rayn"), Button.inline("Nekoray (Throne)", data="Download_Throne")],
    [Button.inline("Streisand", data="IOS_streisand"), Button.inline("FairVPN", data="IOS_fairvpn")],
    [Button.inline("Happ Android", data="Download_happandroid")],
]


inline_back = [[Button.inline("بازگشت", data="backTOhelp")]]
