"""WebApp DTOs: per-service usage chart (daily series and per-day node breakdown).

Raw fields only (bytes, ISO dates, plain numbers) -- the webapp frontend formats
everything itself for bilingual display, unlike the Telegram bot's shared
formatting utils in app/telegram/shared/utils/usage_chart.py which stay Persian-only.
"""

from pydantic import BaseModel, Field


class WebAppUsageChartDayItem(BaseModel):
    date: str
    bytes: int


class WebAppUsageChartSeriesItem(BaseModel):
    name: str
    color: str
    points: list[WebAppUsageChartDayItem] = Field(default_factory=list)


class WebAppUsageChartNodeItem(BaseModel):
    name: str
    bytes: int
    percent: int


class WebAppUsageChartRequest(BaseModel):
    code: int = Field(..., description="Service code")
    days: int = Field(7, ge=1, le=30)
    page: int = Field(0, ge=0)
    day: str | None = Field(None, description="ISO date for per-node day detail")
    session_token: str | None = Field(None, description="Session token from login")
    init_data: str | None = Field(None, description="Telegram init data")


class WebAppUsageChartResponse(BaseModel):
    ok: bool
    mode: str = "chart"
    days: int = 7
    page: int = 0
    total_pages: int = 1
    daily_points: list[WebAppUsageChartDayItem] = Field(default_factory=list)
    series: list[WebAppUsageChartSeriesItem] = Field(default_factory=list)
    available_nodes: list[str] = Field(default_factory=list)
    trend_percent: float | None = None
    trend_direction: str | None = None
    period_total_bytes: int | None = None
    avg_daily_bytes: int | None = None
    peak_date: str | None = None
    peak_value_bytes: int | None = None
    day_total_bytes: int | None = None
    nodes: list[WebAppUsageChartNodeItem] = Field(default_factory=list)
    error: str | None = None
