"""Per-service usage chart: daily series across nodes and per-day node breakdown."""

from datetime import date, datetime, time as dt_time

from fastapi import APIRouter

from app.models.webapp import (
    WebAppUsageChartDayItem,
    WebAppUsageChartNodeItem,
    WebAppUsageChartRequest,
    WebAppUsageChartResponse,
    WebAppUsageChartSeriesItem,
)
from app.routers.webapp.auth import authenticate_user
from app.routers.webapp.services import _resolve_owned_service
from app.services.billing.renewal import require_panel_userid
from app.telegram.shared.utils.usage_chart import (
    CHART_SERIES_COLORS,
    IRAN_TZ,
    PERIOD_OPTIONS,
    _compute_usage_trend,
    _day_label,
    fetch_day_node_usage,
    fetch_usage_chart_series,
)
from app.utils.formatting.dates import Time_Date
from app.utils.formatting.traffic import format_size

router = APIRouter()


@router.post("/webapp/services/usage-chart", response_model=WebAppUsageChartResponse)
async def get_webapp_usage_chart(request: WebAppUsageChartRequest) -> WebAppUsageChartResponse:
    """Daily usage chart or per-day node breakdown."""

    try:
        user_id = await authenticate_user(
            init_data=request.init_data,
            session_token=request.session_token,
        )
        service, panel = await _resolve_owned_service(request.code, user_id)
        days = request.days if request.days in PERIOD_OPTIONS else 7
        panel_userid = require_panel_userid(service)

        if request.day:
            day_value = date.fromisoformat(request.day)
            node_points = await fetch_day_node_usage(panel, panel_userid, day_value)
            today = datetime.now(IRAN_TZ).date()
            day_total = sum(value for _, value in node_points)
            nodes = []
            for name, value in node_points:
                pct = round((value / day_total) * 100) if day_total else 0
                nodes.append(
                    WebAppUsageChartNodeItem(
                        name=name,
                        bytes=value,
                        size_text=format_size(value, decimal_places=1),
                        percent=pct,
                    )
                )
            return WebAppUsageChartResponse(
                ok=True,
                mode="day",
                days=days,
                page=request.page,
                day_label=_day_label(day_value, today),
                day_jalali=Time_Date(datetime.combine(day_value, dt_time.min, tzinfo=IRAN_TZ))["j"],
                day_total_text=format_size(day_total, decimal_places=1) if day_total else "0 B",
                nodes=nodes,
            )

        chart_dates, node_daily, daily_raw = await fetch_usage_chart_series(panel, panel_userid, days=days)
        today = datetime.now(IRAN_TZ).date()

        daily_points = [
            WebAppUsageChartDayItem(
                date=day.isoformat(),
                label=_day_label(day, today),
                bytes=value,
                size_text=format_size(value, decimal_places=1),
            )
            for day, value in daily_raw
        ]

        series_items: list[WebAppUsageChartSeriesItem] = []
        sorted_nodes = sorted(
            node_daily.items(),
            key=lambda item: sum(item[1].values()),
            reverse=True,
        )
        for idx, (node_name, day_map) in enumerate(sorted_nodes):
            if sum(day_map.values()) <= 0:
                continue
            color = CHART_SERIES_COLORS[idx % len(CHART_SERIES_COLORS)]
            points = [
                WebAppUsageChartDayItem(
                    date=day.isoformat(),
                    label=_day_label(day, today),
                    bytes=day_map.get(day, 0),
                    size_text=format_size(day_map.get(day, 0), decimal_places=1),
                )
                for day in chart_dates
            ]
            series_items.append(WebAppUsageChartSeriesItem(name=node_name, color=color, points=points))

        period_total = sum(value for _, value in daily_raw)
        avg_value = period_total // len(daily_raw) if daily_raw else 0
        peak_day, peak_value = max(daily_raw, key=lambda item: item[1]) if daily_raw else (today, 0)
        trend_percent, trend_label = _compute_usage_trend(daily_raw)

        return WebAppUsageChartResponse(
            ok=True,
            mode="chart",
            days=days,
            page=0,
            total_pages=1,
            daily_points=daily_points,
            series=series_items,
            available_nodes=[item.name for item in series_items],
            trend_percent=trend_percent,
            trend_label=trend_label,
            period_total_text=format_size(period_total, decimal_places=1),
            avg_daily_text=format_size(avg_value, decimal_places=1),
            peak_label=_day_label(peak_day, today),
            peak_value_text=format_size(peak_value, decimal_places=1),
            page_total_text=format_size(period_total, decimal_places=1),
        )
    except ValueError as e:
        return WebAppUsageChartResponse(ok=False, error=str(e))
    except Exception as e:
        return WebAppUsageChartResponse(ok=False, error=str(e))
