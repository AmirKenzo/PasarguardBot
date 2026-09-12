from __future__ import annotations


def format_size(size_bytes, decimal_places=0):
    """Convert bytes to a human-readable Persian traffic label."""
    if size_bytes is None:
        return "نامشخص"
    if size_bytes < 0:
        return f"-{format_size(abs(size_bytes), decimal_places)} (حجم اکانت شما تمام شده)"

    if size_bytes < 1024:
        return f"{size_bytes} بایت"
    if size_bytes < 1048576:
        return f"{size_bytes / 1024:.{decimal_places}f} کیلوبایت"
    if size_bytes < 1073741824:
        return f"{size_bytes / 1048576:,.{decimal_places}f} مگابایت"
    return f"{size_bytes / 1073741824:,.{decimal_places}f} گیگابایت"


def format_usage_progress_bar(used_bytes, total_bytes, blocks: int = 10) -> str:
    """Build a Telegram-friendly usage progress bar based on consumed traffic."""
    try:
        used = max(int(used_bytes or 0), 0)
        total = int(total_bytes or 0)
    except (TypeError, ValueError):
        return "نامشخص"

    if total <= 0:
        return "♾️ نامحدود"

    percent = min(max(round((used / total) * 100), 0), 100)
    filled_blocks = min(max(round((percent / 100) * blocks), 0), blocks)
    empty_blocks = blocks - filled_blocks

    if percent >= 100:
        marker = "🔴"
        filled = "🟥"
    elif percent >= 80:
        marker = "🟠"
        filled = "🟧"
    else:
        marker = "🟢"
        filled = "🟩"

    return f"{marker} {filled * filled_blocks}{'⬜️' * empty_blocks} {percent}%"


def format_ip_limit(ip_limit):
    """Format IP limit for display. 0 means unlimited."""
    if ip_limit is None or ip_limit == 0:
        return "بدون محدودیت کاربر"
    return f"{ip_limit} کاربر"
