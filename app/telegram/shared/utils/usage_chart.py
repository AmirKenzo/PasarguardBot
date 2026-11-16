"""Fetch and render daily usage charts from Pasarguard panel API."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, time, timedelta
from typing import Any

import pytz
from pasarguard import Period
from telethon import Button

from app.logger import get_logger
from app.services.panels.api_client import PasarguardAPI
from app.services.panels.nodes import format_node_name_for_display
from app.utils.formatting.dates import Time_Date
from app.utils.formatting.traffic import format_size

logger = get_logger(__name__)

IRAN_TZ = pytz.timezone("Asia/Tehran")
DAYS_PER_PAGE = 7
PERIOD_OPTIONS = (7, 14, 30)
CHART_SERIES_COLORS = ("#eab308", "#a855f7", "#ec4899", "#22d3ee", "#34d399", "#f97316", "#6366f1", "#14b8a6")
BAR_WIDTH = 12
NODE_NAME_WIDTH = 22


def _day_bounds_utc(day: datetime.date) -> tuple[datetime, datetime]:
    start_local = IRAN_TZ.localize(datetime.combine(day, time.min))
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


def _aggregate_daily_points(usage_stats: Any) -> list[tuple[datetime.date, int]]:
    daily: dict[datetime.date, int] = {}
    for stat_list in (getattr(usage_stats, "stats", None) or {}).values():
        for stat in stat_list:
            period_start = getattr(stat, "period_start", None)
            if not period_start:
                continue
            if period_start.tzinfo is None:
                period_start = period_start.replace(tzinfo=UTC)
            day = period_start.astimezone(IRAN_TZ).date()
            daily[day] = daily.get(day, 0) + int(getattr(stat, "total_traffic", 0) or 0)
    return sorted(daily.items(), key=lambda item: item[0], reverse=True)


async def _fetch_node_name_map(api: PasarguardAPI, token: str) -> dict[str, str]:
    try:
        response = await api.get_nodes_simple(token=token, all=True)
        return {str(node.id): node.name for node in response.nodes if node.name}
    except Exception as e:
        logger.warning("Could not fetch node names for usage chart: %s", e)
        return {}


def _resolve_node_display_name(node_key: str, panel: Any, name_map: dict[str, str]) -> str:
    raw_name = name_map.get(str(node_key).strip())
    if not raw_name and str(node_key).isdigit():
        raw_name = name_map.get(str(int(node_key)))
    if not raw_name:
        raw_name = node_key
    return format_node_name_for_display(str(raw_name), panel)


def _aggregate_node_points(
    usage_stats: Any,
    panel: Any,
    name_map: dict[str, str],
) -> list[tuple[str, int]]:
    nodes: dict[str, int] = {}
    for node_key, stat_list in (getattr(usage_stats, "stats", None) or {}).items():
        display_name = _resolve_node_display_name(str(node_key), panel, name_map)
        total = sum(int(getattr(stat, "total_traffic", 0) or 0) for stat in stat_list)
        if total > 0:
            nodes[display_name] = nodes.get(display_name, 0) + total
    return sorted(nodes.items(), key=lambda item: item[1], reverse=True)


def _day_label(day: datetime.date, today: datetime.date) -> str:
    delta = (today - day).days
    if delta == 0:
        return "امروز"
    if delta == 1:
        return "دیروز"
    if 2 <= delta <= 6:
        return f"{delta} روز پیش"
    return Time_Date(datetime.combine(day, time.min, tzinfo=IRAN_TZ))["j"]


def _render_bar(value: int, max_value: int, width: int = BAR_WIDTH) -> str:
    if max_value <= 0 or value <= 0:
        return "░" * width
    filled = max(1, round((value / max_value) * width)) if value > 0 else 0
    filled = min(filled, width)
    return "█" * filled + "░" * (width - filled)


def _format_compact_size(value: int) -> str:
    if value >= 1073741824:
        return f"{value / 1073741824:.1f} GB"
    if value >= 1048576:
        return f"{value / 1048576:.0f} MB"
    if value >= 1024:
        return f"{value / 1024:.0f} KB"
    return f"{value} B"


async def fetch_daily_usage(
    panel: Any,
    panel_userid: int,
    *,
    days: int = 30,
) -> list[tuple[datetime.date, int]]:
    now_utc = datetime.now(tz=UTC)
    start_utc = now_utc - timedelta(days=days)
    api = PasarguardAPI(panel.base_url)
    usage = await api.get_user_usage_by_id(
        user_id=panel_userid,
        token=panel.cookie,
        period=Period.DAY,
        group_by_node=False,
        start=start_utc,
        end=now_utc,
    )
    return _aggregate_daily_points(usage)


def _aggregate_node_daily_series(
    usage_stats: Any,
    panel: Any,
    name_map: dict[str, str],
) -> tuple[list[datetime.date], dict[str, dict[datetime.date, int]]]:
    node_daily: dict[str, dict[datetime.date, int]] = {}
    all_dates: set[datetime.date] = set()

    for node_key, stat_list in (getattr(usage_stats, "stats", None) or {}).items():
        display_name = _resolve_node_display_name(str(node_key), panel, name_map)
        bucket = node_daily.setdefault(display_name, {})
        for stat in stat_list:
            period_start = getattr(stat, "period_start", None)
            if not period_start:
                continue
            if period_start.tzinfo is None:
                period_start = period_start.replace(tzinfo=UTC)
            day = period_start.astimezone(IRAN_TZ).date()
            all_dates.add(day)
            traffic = int(getattr(stat, "total_traffic", 0) or 0)
            bucket[day] = bucket.get(day, 0) + traffic

    return sorted(all_dates), node_daily


def _compute_usage_trend(daily_totals: list[tuple[datetime.date, int]]) -> tuple[float, str]:
    if len(daily_totals) < 4:
        return 0.0, "ثابت"
    ordered = sorted(daily_totals, key=lambda item: item[0])
    mid = len(ordered) // 2
    first_half = sum(value for _, value in ordered[:mid])
    second_half = sum(value for _, value in ordered[mid:])
    if first_half <= 0:
        return (100.0 if second_half > 0 else 0.0), "افزایشی" if second_half > 0 else "ثابت"
    change = ((second_half - first_half) / first_half) * 100
    if change > 5:
        return round(change, 1), "افزایشی"
    if change < -5:
        return round(abs(change), 1), "کاهشی"
    return round(abs(change), 1), "ثابت"


async def fetch_usage_chart_series(
    panel: Any,
    panel_userid: int,
    *,
    days: int = 7,
) -> tuple[list[datetime.date], dict[str, dict[datetime.date, int]], list[tuple[datetime.date, int]]]:
    now_utc = datetime.now(tz=UTC)
    start_utc = now_utc - timedelta(days=days)
    api = PasarguardAPI(panel.base_url)
    usage, name_map = await asyncio.gather(
        api.get_user_usage_by_id(
            user_id=panel_userid,
            token=panel.cookie,
            period=Period.DAY,
            group_by_node=True,
            start=start_utc,
            end=now_utc,
        ),
        _fetch_node_name_map(api, panel.cookie),
    )
    dates, node_daily = _aggregate_node_daily_series(usage, panel, name_map)
    daily_totals: list[tuple[datetime.date, int]] = []
    for day in dates:
        total = sum(node_map.get(day, 0) for node_map in node_daily.values())
        daily_totals.append((day, total))
    return dates, node_daily, daily_totals


async def fetch_day_node_usage(
    panel: Any,
    panel_userid: int,
    day: datetime.date,
) -> list[tuple[str, int]]:
    start_utc, end_utc = _day_bounds_utc(day)
    api = PasarguardAPI(panel.base_url)
    usage, name_map = await asyncio.gather(
        api.get_user_usage_by_id(
            user_id=panel_userid,
            token=panel.cookie,
            period=Period.DAY,
            group_by_node=True,
            start=start_utc,
            end=end_utc,
        ),
        _fetch_node_name_map(api, panel.cookie),
    )
    return _aggregate_node_points(usage, panel, name_map)


def build_usage_chart_message(
    *,
    username: str,
    service_code: int | str,
    daily_points: list[tuple[datetime.date, int]],
    days: int,
    page: int,
) -> str:
    today = datetime.now(IRAN_TZ).date()
    page_points = daily_points[page * DAYS_PER_PAGE : (page + 1) * DAYS_PER_PAGE]
    total_pages = max(1, (len(daily_points) + DAYS_PER_PAGE - 1) // DAYS_PER_PAGE)

    if not page_points:
        return (
            f"📊 **نمودار مصرف روزانه**\n"
            f"🔷 کانفیگ: `{username}`\n"
            f"#⃣ کد: `{service_code}`\n\n"
            "ℹ️ در این بازه زمانی مصرفی ثبت نشده است."
        )

    page_total = sum(value for _, value in page_points)
    period_total = sum(value for _, value in daily_points)
    max_value = max(value for _, value in page_points) or 1
    avg_value = period_total // len(daily_points) if daily_points else 0
    peak_day, peak_value = max(daily_points, key=lambda item: item[1]) if daily_points else (today, 0)

    chart_lines = []
    for day, value in page_points:
        label = _day_label(day, today).ljust(10)[:10]
        bar = _render_bar(value, max_value)
        size = _format_compact_size(value).rjust(8)
        chart_lines.append(f"{label} {bar} {size}")

    chart_block = "\n".join(chart_lines)
    period_label = {7: "۷ روز", 14: "۱۴ روز", 30: "۳۰ روز"}.get(days, f"{days} روز")

    return (
        f"📊 **نمودار مصرف روزانه** ({period_label})\n"
        f"🔷 کانفیگ: `{username}`\n"
        f"#⃣ کد: `{service_code}`\n"
        f"📄 صفحه {page + 1} از {total_pages}\n\n"
        f"^qc^{chart_block}^qc^\n\n"
        f"📈 **مجموع بازه:** {format_size(period_total, decimal_places=1)}\n"
        f"📊 **میانگین روزانه:** {format_size(avg_value, decimal_places=1)}\n"
        f"🔝 **بیشترین مصرف:** {_day_label(peak_day, today)} — {format_size(peak_value, decimal_places=1)}\n"
        f"📋 **مجموع این صفحه:** {format_size(page_total, decimal_places=1)}"
    )


def build_day_detail_message(
    *,
    username: str,
    service_code: int | str,
    day: datetime.date,
    node_points: list[tuple[str, int]],
) -> str:
    today = datetime.now(IRAN_TZ).date()
    day_title = _day_label(day, today)
    jalali = Time_Date(datetime.combine(day, time.min, tzinfo=IRAN_TZ))["j"]

    if not node_points:
        return (
            f"📍 **جزئیات مصرف — {day_title}**\n"
            f"📅 {jalali}\n"
            f"🔷 کانفیگ: `{username}`\n\n"
            "ℹ️ مصرفی برای این روز ثبت نشده است."
        )

    day_total = sum(value for _, value in node_points)
    max_value = max(value for _, value in node_points) or 1
    lines = []
    for idx, (node_name, value) in enumerate(node_points, start=1):
        pct = round((value / day_total) * 100) if day_total else 0
        bar = _render_bar(value, max_value, width=10)
        name = node_name if len(node_name) <= NODE_NAME_WIDTH else node_name[: NODE_NAME_WIDTH - 1] + "…"
        lines.append(f"{idx:2}. 📍 {name.ljust(NODE_NAME_WIDTH)} {bar} {_format_compact_size(value)} ({pct}%)")

    chart_block = "\n".join(lines)
    return (
        f"📍 **جزئیات مصرف — {day_title}**\n"
        f"📅 {jalali}\n"
        f"🔷 کانفیگ: `{username}`\n"
        f"#⃣ کد: `{service_code}`\n\n"
        f"^qc^{chart_block}^qc^\n\n"
        f"📦 **مجموع روز:** {format_size(day_total, decimal_places=1)}\n"
        f"🌐 **تعداد لوکیشن:** {len(node_points)}"
    )


def build_usage_chart_buttons(
    service_code: int | str,
    *,
    days: int,
    page: int,
    daily_points: list[tuple[datetime.date, int]],
    back_data: str,
) -> list:
    total_pages = max(1, (len(daily_points) + DAYS_PER_PAGE - 1) // DAYS_PER_PAGE)
    page_points = daily_points[page * DAYS_PER_PAGE : (page + 1) * DAYS_PER_PAGE]

    rows: list[list] = []
    period_row = []
    for option in PERIOD_OPTIONS:
        label = f"{'• ' if option == days else ''}{option} روز"
        period_row.append(Button.inline(label, data=f"UsageChart:{service_code}:{option}:0"))
    rows.append(period_row)

    nav_row = []
    if page > 0:
        nav_row.append(Button.inline("◀️ قبلی", data=f"UsageChart:{service_code}:{days}:{page - 1}"))
    if page < total_pages - 1:
        nav_row.append(Button.inline("بعدی ▶️", data=f"UsageChart:{service_code}:{days}:{page + 1}"))
    if nav_row:
        rows.append(nav_row)

    for day, value in page_points:
        if value <= 0:
            continue
        today = datetime.now(IRAN_TZ).date()
        label = f"📍 {_day_label(day, today)} — {_format_compact_size(value)}"
        rows.append([Button.inline(label, data=f"UsageChartDay:{service_code}:{day.isoformat()}:{days}:{page}")])

    rows.append([Button.inline("🔙 بازگشت به سرویس", data=back_data)])
    return rows


def build_day_detail_buttons(
    service_code: int | str,
    *,
    days: int,
    page: int,
    back_data: str,
) -> list:
    return [
        [Button.inline("🔙 بازگشت به نمودار", data=f"UsageChart:{service_code}:{days}:{page}")],
        [Button.inline("🔙 بازگشت به سرویس", data=back_data)],
    ]
