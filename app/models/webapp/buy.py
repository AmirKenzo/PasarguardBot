"""WebApp DTOs: new-purchase flow (panel/plan discovery, username, preview, confirm)."""

from pydantic import BaseModel, Field

from app.models.webapp.common import WebAppAuthRequest


class WebAppBuyPanelItem(BaseModel):
    code: int
    name: str
    display_mode: str = "classic"
    durations: list[int] = Field(default_factory=list)


class WebAppBuyOptionsRequest(WebAppAuthRequest):
    """Request buy options."""


class WebAppBuyOptionsResponse(BaseModel):
    ok: bool
    single_panel_buy_mode: bool = False
    panels: list[WebAppBuyPanelItem] = Field(default_factory=list)
    error: str | None = None


class WebAppBuyPlanItem(BaseModel):
    """Raw plan fields only -- the webapp frontend builds its own bilingual plan
    label from storage/plan_type/data_limit_reset_strategy rather than a
    server-formatted Persian plan_name."""

    id: int
    storage: float
    duration: int
    price: int
    plan_type: str = "volume"
    data_limit_reset_strategy: str = "no_reset"
    ip_limit: int = 0


class WebAppBuyPlansRequest(WebAppAuthRequest):
    panel_code: int = Field(..., description="Selected panel code")
    duration: int | None = Field(None, description="Optional selected duration")


class WebAppBuyPlansResponse(BaseModel):
    ok: bool
    panel: WebAppBuyPanelItem | None = None
    durations: list[int] = Field(default_factory=list)
    plans: list[WebAppBuyPlanItem] = Field(default_factory=list)
    error: str | None = None


class WebAppBuyUsernameRequest(WebAppAuthRequest):
    panel_code: int = Field(..., description="Selected panel code")


class WebAppBuyUsernameResponse(BaseModel):
    ok: bool
    username: str | None = None
    error: str | None = None


class WebAppBuyPreviewRequest(WebAppAuthRequest):
    panel_code: int = Field(..., description="Selected panel code")
    plan_id: int = Field(..., description="Selected plan id")
    username: str = Field(..., description="Requested config username")
    discount_code: str | None = Field(None, description="Optional discount code")


class WebAppBuyPreviewResponse(BaseModel):
    ok: bool
    panel_name: str | None = None
    plan: WebAppBuyPlanItem | None = None
    username: str | None = None
    base_price: int | None = None
    final_price: int | None = None
    discount_percent: int = 0
    balance: int | None = None
    balance_after: int | None = None
    can_pay: bool = False
    locations: list[str] = Field(default_factory=list)
    error: str | None = None


class WebAppBuyConfirmRequest(WebAppBuyPreviewRequest):
    """Confirm a WebApp VPN purchase."""


class WebAppBuyConfirmResponse(BaseModel):
    ok: bool
    message: str | None = None
    service_code: int | None = None
    username: str | None = None
    panel_name: str | None = None
    volume_bytes: int | None = None
    duration: int | None = None
    ip_limit: int | None = None
    subscription_url: str | None = None
    subscription_links_text: str | None = None
    single_config_links_text: str | None = None
    amount_paid: int | None = None
    new_balance: int | None = None
    creation_time_ms: int | None = None
    error: str | None = None
