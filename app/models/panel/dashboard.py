"""Admin panel DTOs: dashboard overview."""

from pydantic import BaseModel, Field

from app.models.panel.common import PanelResponse


class PanelStats(BaseModel):
    users_total: int = 0
    users_blocked: int = 0
    users_today: int = 0
    wallet_total: int = 0
    services_total: int = 0
    services_active: int = 0
    services_expired: int = 0
    income_today: int = 0
    income_month: int = 0
    pending_tx: int = 0
    panels_total: int = 0
    resellers_active: int = 0


class PanelDayPoint(BaseModel):
    ts: int = Field(..., description="Unix timestamp of the start of the day")
    revenue: int = 0
    signups: int = 0


class PanelDashboardResponse(PanelResponse):
    stats: PanelStats = Field(default_factory=PanelStats)
    series: list[PanelDayPoint] = Field(default_factory=list)
    badges: dict[str, int] = Field(default_factory=dict)


class PanelMeResponse(PanelResponse):
    """Who the caller is, for the frontend to render the shell."""

    user_id: int = 0
    username: str = ""
    badges: dict[str, int] = Field(default_factory=dict)
