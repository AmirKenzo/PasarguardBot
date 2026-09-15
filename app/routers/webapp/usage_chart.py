"""Per-service usage chart: daily series across nodes and per-day node breakdown."""

from datetime import date

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
    PERIOD_OPTIONS,
    _compute_usage_trend,
    fetch_day_node_usage,
    fetch_usage_chart_series,
)

router = APIRouter()

_TREND_DIRECTION_MAP = {"افزایشی": "up", "کاهشی": "down", "ثابت": "stable"}


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
            day_total = sum(value for _, value in node_points)
            nodes = [
                WebAppUsageChartNodeItem(
                    name=name,
                    bytes=value,
                    percent=round((value / day_total) * 100) if day_total else 0,
                )
                for name, value in node_points
            ]
            return WebAppUsageChartResponse(
                ok=True,
                mode="day",
                days=days,
                page=request.page,
                day_total_bytes=day_total,
                nodes=nodes,
            )

        chart_dates, node_daily, daily_raw = await fetch_usage_chart_series(panel, panel_userid, days=days)

        daily_points = [WebAppUsageChartDayItem(date=day.isoformat(), bytes=value) for day, value in daily_raw]

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
            points = [WebAppUsageChartDayItem(date=day.isoformat(), bytes=day_map.get(day, 0)) for day in chart_dates]
            series_items.append(WebAppUsageChartSeriesItem(name=node_name, color=color, points=points))

        period_total = sum(value for _, value in daily_raw)
        avg_value = period_total // len(daily_raw) if daily_raw else 0
        peak_day, peak_value = max(daily_raw, key=lambda item: item[1]) if daily_raw else (date.today(), 0)
        trend_percent, trend_label_fa = _compute_usage_trend(daily_raw)

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
            trend_direction=_TREND_DIRECTION_MAP.get(trend_label_fa, "stable"),
            period_total_bytes=period_total,
            avg_daily_bytes=avg_value,
            peak_date=peak_day.isoformat(),
            peak_value_bytes=peak_value,
        )
    except ValueError as e:
        return WebAppUsageChartResponse(ok=False, error=str(e))
    except Exception as e:
        return WebAppUsageChartResponse(ok=False, error=str(e))
