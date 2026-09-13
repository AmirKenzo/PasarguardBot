"""Admin panel DTOs: sales reports and the panel activity log."""

from typing import Any

from pydantic import BaseModel, Field

from app.models.panel.common import PagedRequest, PageMeta, PanelRequest, PanelResponse

REPORT_PERIODS = ("today", "week", "month")


class PanelRankRow(BaseModel):
    rank: int
    user_id: int | None = None
    amount: int = 0
    count: int = 0


class PanelReportTotals(BaseModel):
    new_users: int = 0
    services_sold: int = 0
    test_services: int = 0
    manual_approved_sum: int = 0
    auto_approved_sum: int = 0
    pending_sum: int = 0
    pending_count: int = 0


class PanelReportsRequest(PanelRequest):
    period: str = Field("today", description="today | week | month")


class PanelReportsResponse(PanelResponse):
    period: str = "today"
    period_start: int = 0
    periods: list[str] = Field(default_factory=lambda: list(REPORT_PERIODS))
    totals: PanelReportTotals = Field(default_factory=PanelReportTotals)
    top_recharge: list[PanelRankRow] = Field(default_factory=list)
    top_spenders: list[PanelRankRow] = Field(default_factory=list)
    top_service_counts: list[PanelRankRow] = Field(default_factory=list)


class PanelAuditRow(BaseModel):
    id: int
    admin_id: int | None = None
    admin_username: str | None = None
    action: str
    target_type: str | None = None
    target_id: str | None = None
    detail: dict[str, Any] | None = None
    ip: str | None = None
    created_at: int | None = None


class PanelAuditRequest(PagedRequest):
    action: str = Field("", max_length=64)
    admin_id: int | None = None


class PanelAuditResponse(PanelResponse):
    entries: list[PanelAuditRow] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    meta: PageMeta = Field(default_factory=PageMeta)
