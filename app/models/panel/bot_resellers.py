"""Admin panel DTOs for bot resellers (services, requests, resellers)."""

from pydantic import BaseModel, Field

from app.models.panel.common import PanelRequest, PanelResponse
from app.models.panel.services import PanelPanelOption


class BotServiceRow(BaseModel):
    id: int
    panel_code: int
    panel_name: str | None = None
    name: str
    description: str | None = None
    group_ids: list[int] = Field(default_factory=list)
    price_per_gb: int
    sale_enabled: bool
    max_users: int
    max_user_gb: float
    max_user_days: int
    resellers: int = 0


class BotServicesResponse(PanelResponse):
    services: list[BotServiceRow] = Field(default_factory=list)
    panels: list[PanelPanelOption] = Field(default_factory=list)


class BotServiceGroupsRequest(PanelRequest):
    panel_code: int


class BotServiceGroup(BaseModel):
    id: int
    name: str


class BotServiceGroupsResponse(PanelResponse):
    groups: list[BotServiceGroup] = Field(default_factory=list)


class BotServiceSaveRequest(PanelRequest):
    id: int | None = None
    panel_code: int
    name: str = Field(..., min_length=1, max_length=64)
    description: str | None = Field(None, max_length=500)
    group_ids: list[int] = Field(default_factory=list)
    price_per_gb: int = Field(..., ge=0)
    sale_enabled: bool = True
    max_users: int = Field(0, ge=0)
    max_user_gb: float = Field(0, ge=0)
    max_user_days: int = Field(0, ge=0)


class BotServiceToggleRequest(PanelRequest):
    id: int
    sale_enabled: bool


class BotSettings(BaseModel):
    sale_mode: bool = True


class BotSettingsResponse(PanelResponse):
    settings: BotSettings = Field(default_factory=BotSettings)
    global_sale_mode: bool = True
    services_on_sale: int = 0


class BotSettingsSaveRequest(PanelRequest):
    settings: BotSettings


class BotGrantTerms(BaseModel):
    """Per-reseller values; None keeps the service default."""

    price_per_gb: int | None = Field(None, ge=0)
    max_users: int | None = Field(None, ge=0)
    max_user_gb: float | None = Field(None, ge=0)
    max_user_days: int | None = Field(None, ge=0)


class BotGrantRow(BaseModel):
    id: int
    reseller_id: int
    telegram_id: int
    service_id: int
    service_name: str
    status: str
    price_per_gb: int
    max_users: int
    max_user_gb: float
    max_user_days: int
    own_terms: BotGrantTerms
    users: int = 0
    balance: int = 0
    reject_reason: str | None = None
    requested_at: int
    decided_at: int | None = None


class BotRequestsResponse(PanelResponse):
    requests: list[BotGrantRow] = Field(default_factory=list)


class BotGrantIdRequest(PanelRequest):
    grant_id: int


class BotGrantApproveRequest(BotGrantIdRequest):
    terms: BotGrantTerms = Field(default_factory=BotGrantTerms)


class BotGrantRejectRequest(BotGrantIdRequest):
    reason: str | None = Field(None, max_length=300)


class BotGrantManualRequest(PanelRequest):
    telegram_id: int
    service_id: int
    terms: BotGrantTerms = Field(default_factory=BotGrantTerms)


class BotResellerRow(BaseModel):
    id: int
    telegram_id: int
    status: str
    balance: int
    users: int
    usage_24h_bytes: int = 0
    usage_24h_amount: int = 0
    services: list[str] = Field(default_factory=list)
    username_prefix: str = ""
    username_suffix: str = ""
    created_at: int


class BotResellersResponse(PanelResponse):
    resellers: list[BotResellerRow] = Field(default_factory=list)


class BotResellerIdRequest(PanelRequest):
    id: int


class BotResellerNamingRequest(BotResellerIdRequest):
    username_prefix: str = Field(default="", max_length=16)
    username_suffix: str = Field(default="", max_length=16)


class BotResellerUserRow(BaseModel):
    id: int
    name: str
    username: str
    service_name: str
    disabled_by: str | None = None
    billed_bytes: int = 0
    cost: int = 0
    note: str | None = None
    created_at: int


class BotResellerDetailResponse(PanelResponse):
    reseller: BotResellerRow | None = None
    grants: list[BotGrantRow] = Field(default_factory=list)
    users: list[BotResellerUserRow] = Field(default_factory=list)


class BotResellerUserIdRequest(PanelRequest):
    user_id: int
