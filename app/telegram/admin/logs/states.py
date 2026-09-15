"""State constants for admin log management."""

LOG_MANAGEMENT_STEP = "LogManagement"
SHOW_LOG_STATUS_STEP = "ShowLogStatus"

SET_LOG_CHANNEL_PREFIX = "SetLogChannel_"
SET_LOG_SUPERGROUP_PREFIX = "SetLogSupergroup_"
SET_LOG_TOPIC_PREFIX = "SetLogTopic_"

LOG_INPUT_STEP_PREFIXES = (
    SET_LOG_CHANNEL_PREFIX,
    SET_LOG_SUPERGROUP_PREFIX,
    SET_LOG_TOPIC_PREFIX,
)

SET_ALL_LOG_TYPE = "all"

BACK_TO_LOG_MANAGEMENT = "BackToLogManagement"
BACK_TO_ADMIN_PANEL = "LogBackToAdmin"
LOG_SHOW_STATUS = "log_show_status"
LOG_SET_ALL = "log_set_all"
LOG_TYPE_PREFIX = "log_type:"

ALL_LOG_TYPES: tuple[tuple[str, str], ...] = (
    ("manual_card", "💳 کارت به کارت دستی"),
    ("crypto", "💱 واریزی ارزی"),
    ("reseller", "🏢 لاگ نمایندگی‌ها"),
    ("other", "📋 سایر لاگ‌ها"),
    ("backup", "🗄 بکاپ ربات"),
    ("app_files", "📦 کانال آپدیت برنامه‌ها"),
    ("purchase", "🛍 گزارش خرید (کانال عمومی)"),
)
