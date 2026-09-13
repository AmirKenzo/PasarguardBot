"""WebApp DTOs: services list/detail, config links, clients, link/subscription change."""

from pydantic import BaseModel, Field

from app.models.webapp.common import ServiceButtons, ServiceStatus


class WebAppChangeLinkRequest(BaseModel):
    """Request to change user's proxy link."""

    code: int = Field(..., description="Service code")
    init_data: str | None = Field(None, description="Telegram init data")
    session_token: str | None = Field(None, description="Session token from OTP login")


class WebAppChangeSubscriptionRequest(BaseModel):
    """Request to change user's subscription."""

    code: int = Field(..., description="Service code")
    init_data: str | None = Field(None, description="Telegram init data")
    session_token: str | None = Field(None, description="Session token from OTP login")


class WebAppServicesRequest(BaseModel):
    """Request for services list."""

    session_token: str | None = Field(None, description="Session token from login")
    init_data: str | None = Field(None, description="Telegram init data")
    page: int = Field(1, ge=1, description="Page number")
    limit: int = Field(10, ge=1, le=30, description="Items per page (max 30)")
    search: str | None = Field(None, description="Search by config name or service code")
    panel_code: int | None = Field(None, description="Filter services by panel (used with panel grouping)")


class PanelGroupItem(BaseModel):
    """A panel with the count of services the user owns in it."""

    panel_code: int
    panel_name: str
    service_count: int


class WebAppServicesResponse(BaseModel):
    """Response for services list endpoint."""

    ok: bool
    services: list[ServiceStatus] | None = None
    total: int = 0
    page: int = 1
    limit: int = 10
    total_pages: int = 0
    grouping_enabled: bool = False
    panel_groups: list[PanelGroupItem] | None = None
    error: str | None = None


class WebAppServiceDetailRequest(BaseModel):
    """Request for single service detail."""

    code: int = Field(..., description="Service code")
    session_token: str | None = Field(None, description="Session token from login")
    init_data: str | None = Field(None, description="Telegram init data")


class WebAppServiceDetailResponse(BaseModel):
    """Response for single service detail."""

    ok: bool
    service: ServiceStatus | None = None
    buttons: ServiceButtons | None = None
    error: str | None = None


class WebAppConfigLinkItem(BaseModel):
    index: int
    name: str
    url: str


class WebAppConfigLinksRequest(BaseModel):
    code: int = Field(..., description="Service code")
    page: int = Field(1, ge=1)
    limit: int = Field(500, ge=1, le=500)
    session_token: str | None = Field(None, description="Session token from login")
    init_data: str | None = Field(None, description="Telegram init data")


class WebAppConfigLinksResponse(BaseModel):
    ok: bool
    links: list[WebAppConfigLinkItem] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    total_pages: int = 0
    error: str | None = None


class WebAppClientItem(BaseModel):
    created_at: int
    user_agent: str | None = None
    app_name: str | None = None
    version: str | None = None
    platform: str | None = None
    ip_address: str | None = None
    hwid: str | None = None


class WebAppClientsRequest(BaseModel):
    code: int = Field(..., description="Service code")
    session_token: str | None = Field(None, description="Session token from login")
    init_data: str | None = Field(None, description="Telegram init data")


class WebAppClientsResponse(BaseModel):
    ok: bool
    clients: list[WebAppClientItem] = Field(default_factory=list)
    error: str | None = None
