"""Keyboard builders for admin send2all."""

from telethon import Button

from app.services.broadcast.payload_format import format_label, selectable_types
from app.services.telegram.rich_message import RICH_MESSAGE_DOCS_URL
from app.telegram.admin.send2all import texts


def active_broadcast_buttons(*, create_mode: str):
    return [
        [Button.inline("➕ ساخت همگانی جدید", data=f"broadcast_create_new:{create_mode}")],
        [Button.inline("📋 همگانی‌های ناتمام", data="broadcast_incomplete_list")],
        [Button.inline("🔙 بازگشت", data="broadcast_menu_back")],
    ]


def broadcast_menu_buttons(*, incomplete_count: int, create_mode: str):
    buttons = [[Button.inline("➕ ساخت همگانی جدید", data=f"broadcast_create_new:{create_mode}")]]
    if incomplete_count > 0:
        buttons.append([Button.inline(f"📋 همگانی‌های ناتمام ({incomplete_count})", data="broadcast_incomplete_list")])
    else:
        buttons.append([Button.inline("📋 همگانی‌های ناتمام", data="broadcast_incomplete_list")])
    buttons.append([Button.inline("🔙 بازگشت", data="broadcast_menu_back")])
    return buttons


def confirm_buttons(job_id: int):
    return [
        [
            Button.inline("✅ تایید و شروع", data=f"broadcast_confirm:{job_id}"),
            Button.inline("🧪 تست به ادمین", data=f"broadcast_test:{job_id}"),
        ],
        [
            Button.inline("⚙️ تنظیمات", data=f"broadcast_settings:{job_id}"),
            Button.inline("❌ انصراف", data=f"broadcast_cancel:{job_id}"),
        ],
    ]


def settings_buttons(job_id: int, job):
    batch_delay_str = texts.format_batch_delay(job.batch_delay_ms)
    return [
        [
            Button.inline(f"⏱️ تاخیر: {job.delay_ms}ms", data=f"broadcast_set_delay:{job_id}"),
            Button.inline(f"📦 دسته: {job.batch_size}", data=f"broadcast_set_batch:{job_id}"),
        ],
        [
            Button.inline(f"⏸️ تاخیر دسته: {batch_delay_str}", data=f"broadcast_set_batch_delay:{job_id}"),
        ],
        [
            Button.inline("🎯 تغییر حالت", data=f"broadcast_set_mode:{job_id}"),
        ],
        [
            Button.inline(
                f"📝 نوع: {format_label(job.payload_json.get('parse_mode'))}",
                data=f"broadcast_set_format:{job_id}",
            ),
        ],
        [
            Button.inline("🔙 بازگشت", data=f"broadcast_back:{job_id}"),
        ],
    ]


def delay_selection_buttons(job_id: int, job):
    buttons = []
    row = []
    for delay in texts.BROADCAST_DELAYS_MS:
        check = "✅ " if delay == job.delay_ms else ""
        row.append(Button.inline(f"{check}{delay}ms", data=f"broadcast_apply_delay:{job_id}:{delay}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([Button.inline("🔙 بازگشت", data=f"broadcast_settings:{job_id}")])
    return buttons


def batch_selection_buttons(job_id: int, job):
    buttons = []
    row = []
    for batch in texts.BROADCAST_BATCH_SIZES:
        check = "✅ " if batch == job.batch_size else ""
        row.append(Button.inline(f"{check}{batch}", data=f"broadcast_apply_batch:{job_id}:{batch}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([Button.inline("🔙 بازگشت", data=f"broadcast_settings:{job_id}")])
    return buttons


def mode_selection_buttons(job_id: int, job):
    buttons = []
    for mode_key, mode_name in texts.MODE_NAMES_SETTINGS.items():
        check = "✅ " if mode_key == job.target_mode else ""
        buttons.append([Button.inline(f"{check}{mode_name}", data=f"broadcast_apply_mode:{job_id}:{mode_key}")])
    buttons.append([Button.inline("🔙 بازگشت", data=f"broadcast_settings:{job_id}")])
    return buttons


def format_selection_buttons(job_id: int, job):
    payload = job.payload_json
    current = payload.get("parse_mode")
    buttons = []
    labels = {"normal": "📝 عادی", "rich": "✨ Rich"}
    for mode in selectable_types(payload):
        check = "✅ " if (current == "rich") == (mode == "rich") else ""
        buttons.append([Button.inline(f"{check}{labels[mode]}", data=f"broadcast_apply_format:{job_id}:{mode}")])
    buttons.append([Button.url("📖 راهنمای Rich Message", url=RICH_MESSAGE_DOCS_URL)])
    buttons.append([Button.inline("🔙 بازگشت", data=f"broadcast_settings:{job_id}")])
    return buttons


def batch_delay_selection_buttons(job_id: int, job):
    buttons = []
    row = []
    for delay_ms in texts.BROADCAST_BATCH_DELAYS_MS:
        check = "✅ " if delay_ms == job.batch_delay_ms else ""
        delay_str = texts.format_batch_delay(delay_ms)
        row.append(Button.inline(f"{check}{delay_str}", data=f"broadcast_apply_batch_delay:{job_id}:{delay_ms}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([Button.inline("🔙 بازگشت", data=f"broadcast_settings:{job_id}")])
    return buttons


def job_detail_buttons(job_id: int, *, status: str):
    buttons = [[Button.inline("📨 دریافت پیام", data=f"broadcast_job_get_msg:{job_id}")]]
    if status == "running":
        buttons.append([Button.inline("⏸️ توقف موقت", data=f"broadcast_pause:{job_id}")])
    elif status == "paused":
        buttons.append([Button.inline("▶️ ادامه", data=f"broadcast_resume:{job_id}")])
    elif status in {"pending_confirm", "queued", "failed"}:
        buttons.append([Button.inline("🔄 ادامه ارسال", data=f"broadcast_job_resend:{job_id}")])
    if status != "running":
        buttons.append([Button.inline("🗑️ حذف همگانی", data=f"broadcast_job_delete:{job_id}")])
    buttons.append([Button.inline("🔙 بازگشت", data="broadcast_incomplete_list")])
    return buttons


def monitor_status_buttons(job_id: int, *, paused: bool):
    if paused:
        return [
            [Button.inline("▶️ ادامه", data=f"broadcast_resume:{job_id}")],
            [Button.inline("❌ لغو", data=f"broadcast_cancel:{job_id}")],
        ]
    return [
        [Button.inline("⏸️ توقف موقت", data=f"broadcast_pause:{job_id}")],
        [Button.inline("❌ لغو", data=f"broadcast_cancel:{job_id}")],
    ]
