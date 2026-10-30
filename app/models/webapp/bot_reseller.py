"""Web app DTOs for the bot reseller panel (raw numbers; the frontend formats them)."""

from pydantic import BaseModel, Field

from app.models.webapp.common import WebAppAuthRequest


class BotResellerOk(BaseModel):
    ok: bool = True
    error: str | None = None


class BotResellerServiceItem(BaseModel):
    id: int
    name: str
    price_per_gb: int
    max_users: int = 0
    max_user_gb: float = 0
    max_user_days: int = 0
    users: int = 0
    usage_24h_bytes: int = 0


class BotResellerStateResponse(BotResellerOk):
    is_reseller: bool = False
    status: str | None = None
    balance: int = 0
    burn_per_hour: int = 0
    runway_hours: float | None = None
    usage_24h_bytes: int = 0
    usage_24h_amount: int = 0
    services: list[BotResellerServiceItem] = Field(default_factory=list)
    pending: list[str] = Field(default_factory=list)
    username_prefix: str = ""
    username_suffix: str = ""


class BotResellerUserItem(BaseModel):
    id: int
    name: str
    username: str = ""
    service_id: int
    service_name: str
    note: str | None = None
    status: str | None = None
    disabled_by: str | None = None
    used_bytes: int = 0
    limit_bytes: int = 0
    expire: int | None = None
    online_at: int | None = None
    cost: int = 0
    live: bool = False


class BotResellerUsersRequest(WebAppAuthRequest):
    service_id: int | None = None


class BotResellerUsersResponse(BotResellerOk):
    users: list[BotResellerUserItem] = Field(default_factory=list)
    live_error: bool = False


class BotResellerUserRequest(WebAppAuthRequest):
    id: int


class BotResellerUserResponse(BotResellerOk):
    user: BotResellerUserItem | None = None
    subscription_url: str | None = None


class BotResellerCreateRequest(WebAppAuthRequest):
    service_id: int
    name: str = Field(..., max_length=32)
    gb: float = Field(0, ge=0)
    days: int = Field(0, ge=0)
    note: str | None = Field(None, max_length=200)


class BotResellerEditRequest(WebAppAuthRequest):
    id: int
    gb: float = Field(0, ge=0)
    days: int = Field(0, ge=0)
    note: str | None = Field(None, max_length=200)


class BotResellerToggleRequest(WebAppAuthRequest):
    id: int
    enabled: bool


class BotResellerUsageRow(BaseModel):
    hour: int
    service_id: int
    service_name: str
    bytes: int
    amount: int


class BotResellerUsageResponse(BotResellerOk):
    rows: list[BotResellerUsageRow] = Field(default_factory=list)
