"""Admin panel DTOs: reseller accounts, their billing history and plans."""

from pydantic import BaseModel, Field

from app.models.panel.common import PagedRequest, PageMeta, PanelRequest, PanelResponse
from app.models.panel.plans import BUTTON_STYLE_VALUES
from app.models.panel.services import PanelPanelOption

RESELLER_STATUSES = ("active", "suspended", "expired")


class PanelResellerRow(BaseModel):
    code: int
    telegram_id: int | None = None
    username: str | None = None
    panel_code: int | None = None
    panel: str | None = None
    pricing_mode: str = "fixed"
    purchased_volume: float | None = None
    usage_cap_bytes: int | None = None
    max_users: int | None = None
    createtime: int | None = None
    expiration_time: int | None = None
    status: str = "active"


class PanelResellersRequest(PagedRequest):
    q: str = Field("", max_length=64)
    status: str = Field("", description="empty | active | suspended | expired")


class PanelResellersResponse(PanelResponse):
    resellers: list[PanelResellerRow] = Field(default_factory=list)
    panels: list[PanelPanelOption] = Field(default_factory=list)
    statuses: list[str] = Field(default_factory=lambda: list(RESELLER_STATUSES))
    meta: PageMeta = Field(default_factory=PageMeta)


class PanelResellerSnapshotRow(BaseModel):
    id: int
    used_traffic: int = 0
    billed_amount: int = 0
    snapshot_at: int | None = None


class PanelResellerDetailRequest(PanelRequest):
    code: int


class PanelResellerDetailResponse(PanelResponse):
    reseller: PanelResellerRow | None = None
    snapshots: list[PanelResellerSnapshotRow] = Field(default_factory=list)
    statuses: list[str] = Field(default_factory=lambda: list(RESELLER_STATUSES))


class PanelResellerUpdateRequest(PanelRequest):
    code: int
    status: str = "active"
    usage_cap_gb: float | None = Field(None, ge=0, description="Null removes the cap")
    max_users: int = Field(0, ge=0)
    extend_days: int = Field(0, ge=0, description="Days added to the current expiry")


class PanelResellerDeleteRequest(PanelRequest):
    code: int


class PanelResellerPlanRow(BaseModel):
    id: int
    panel_code: int
    panel: str | None = None
    pricing_mode: str = "fixed"
    price: float = 0
    unit_price: float = 0
    min_volume: float = 0
    max_volume: float = 0
    volume_step: float = 1
    max_users: int = 0
    duration: int = 0
    role_id: int = 0
    role_name: str | None = None
    enable: bool = True
    display_button_text: str | None = None
    button_style: str | None = None
    button_icon: int | None = None


class PanelResellerPlansResponse(PanelResponse):
    plans: list[PanelResellerPlanRow] = Field(default_factory=list)
    panels: list[PanelPanelOption] = Field(default_factory=list)
    pricing_modes: list[str] = Field(default_factory=list)
    button_styles: list[str] = Field(default_factory=lambda: list(BUTTON_STYLE_VALUES))


class PanelResellerPlanSaveRequest(PanelRequest):
    """Create when ``plan_id`` is null, otherwise update that plan."""

    plan_id: int | None = None
    panel_code: int = Field(..., gt=0)
    pricing_mode: str = "fixed"
    price: float = Field(0, ge=0)
    unit_price: float = Field(0, ge=0)
    min_volume: float = Field(0, ge=0)
    max_volume: float = Field(0, ge=0)
    volume_step: float = Field(1, gt=0)
    max_users: int = Field(0, ge=0)
    duration: int = Field(0, ge=0)
    role_id: int = Field(..., ge=0)
    role_name: str = Field("", max_length=64)
    enable: bool = True
    display_button_text: str = Field("", max_length=64)
    button_style: str = Field("", max_length=20)
    button_icon: str = Field("", max_length=64)


class PanelResellerPlanDeleteRequest(PanelRequest):
    plan_id: int
