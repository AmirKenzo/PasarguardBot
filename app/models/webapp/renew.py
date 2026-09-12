"""WebApp DTOs: manual renewal options and confirmation."""

from pydantic import BaseModel, Field


class RenewPlanItem(BaseModel):
    """Single plan for renewal."""

    id: int
    storage: float
    duration: int
    price: int
    plan_name: str
    ip_limit: int = 0


class WebAppRenewOptionsRequest(BaseModel):
    """Request for renewal options (durations and plans)."""

    code: int = Field(..., description="Service code")
    session_token: str | None = Field(None, description="Session token from login")
    init_data: str | None = Field(None, description="Telegram init data")


class WebAppRenewOptionsResponse(BaseModel):
    """Response with renewal options."""

    ok: bool
    service_code: str | None = None
    panel_name: str | None = None
    is_fair_usage: bool = False
    durations: list[int] | None = None
    duration_groups: dict[str, list[int]] | None = None
    plans: list[RenewPlanItem] | None = None
    error: str | None = None


class WebAppRenewConfirmRequest(BaseModel):
    """Request to confirm renewal (with optional discount code)."""

    code: int = Field(..., description="Service code")
    plan_id: int = Field(..., description="Selected plan id")
    discount_code: str | None = Field(None, description="Optional discount code")
    session_token: str | None = Field(None, description="Session token from login")
    init_data: str | None = Field(None, description="Telegram init data")


class WebAppRenewConfirmResponse(BaseModel):
    """Response after renewal confirm."""

    ok: bool
    message: str | None = None
    new_balance: int | None = None
    new_volume: str | None = None
    amount_paid: int | None = None
    config_name: str | None = None
    error: str | None = None
