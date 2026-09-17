"""Admin panel DTOs: the sale plans offered in the bot."""

from pydantic import BaseModel, Field

from app.models.panel.common import PagedRequest, PageMeta, PanelRequest, PanelResponse

PLAN_TYPES = ("volume", "fair_usage")
RESET_STRATEGIES = ("no_reset", "day", "week", "month", "year")
BUTTON_STYLE_VALUES = ("", "primary", "success", "danger")
PLAN_SORT_VALUES = (
    "newest",
    "oldest",
    "price_asc",
    "price_desc",
    "volume_asc",
    "volume_desc",
    "duration_asc",
    "duration_desc",
)


class PanelPlanRow(BaseModel):
    id: int
    panel_code: int
    panel: str | None = None
    storage: float = 0
    duration: int = 0
    price: float = 0
    plan_type: str = "volume"
    data_limit_reset_strategy: str = "no_reset"
    ip_limit: int = 0
    display_button_text: str | None = None
    button_style: str | None = None
    button_icon: int | None = None


class PanelPlansRequest(PagedRequest):
    panel: str = Field("", description="Panel code, or empty for all")
    sort: str = Field("newest", description=" | ".join(PLAN_SORT_VALUES))


class PanelPlansResponse(PanelResponse):
    plans: list[PanelPlanRow] = Field(default_factory=list)
    meta: PageMeta = Field(default_factory=PageMeta)
    plan_types: list[str] = Field(default_factory=lambda: list(PLAN_TYPES))
    reset_strategies: list[str] = Field(default_factory=lambda: list(RESET_STRATEGIES))
    button_styles: list[str] = Field(default_factory=lambda: list(BUTTON_STYLE_VALUES))


class PanelPlanSaveRequest(PanelRequest):
    """Create when ``plan_id`` is null, otherwise update that plan."""

    plan_id: int | None = None
    panel_code: int = Field(..., gt=0)
    storage: float = Field(0, ge=0, description="Gigabytes, zero meaning unlimited")
    duration: int = Field(..., gt=0, description="Days")
    price: float = Field(..., ge=0)
    plan_type: str = "volume"
    data_limit_reset_strategy: str = "no_reset"
    ip_limit: int = Field(0, ge=0)
    display_button_text: str = Field("", max_length=64)
    button_style: str = Field("", max_length=20)
    button_icon: str = Field("", max_length=64, description="Premium emoji id, or empty")


class PanelPlanDeleteRequest(PanelRequest):
    plan_id: int
