"""Shared WebApp DTOs: auth base, user profile, service status, nested types."""

from pydantic import BaseModel, Field


class WebAppUserData(BaseModel):
    """User data from Telegram WebApp."""

    id: int
    username: str | None = None
    first_name: str | None = None
    photo_url: str | None = None


class WebAppAuthRequest(BaseModel):
    """Common WebApp auth body."""

    session_token: str | None = Field(None, description="Session token from login")
    init_data: str | None = Field(None, description="Telegram init data")


class ServiceStatus(BaseModel):
    """Service status information."""

    code: str
    username: str
    panel_name: str | None = None
    status: str | None = None
    status_text: str
    used_traffic: str = "0 B"
    remaining_traffic: str = "0 B"
    total_traffic: str = "0 B"
    used_traffic_bytes: int = 0
    remaining_traffic_bytes: int = 0
    total_traffic_bytes: int = 0
    expiration_time: str = "نامشخص"
    subscription_url: str = "نامشخص"
    ip_limit_text: str | None = None
    helper_subscription_url: str | None = None
    config_value: str | None = None
    lifetime_used_traffic: str | None = None
    last_connection: str | None = None
    last_edit: str | None = None
    reset_strategy_text: str | None = None
    total_possible_traffic: str | None = None
    single_config_links: list[str] = Field(default_factory=list)


class ServiceButtons(BaseModel):
    """Button visibility flags from panel/settings."""

    copy_link: bool = False
    change_link: bool = False
    change_sub: bool = False
    tamdid: bool = False
    extend_time: bool = False
    extra_volume: bool = False
    qr: bool = False
    other_links: bool = False
    transfer_config: bool = False
    client_list: bool = False
    usage_chart: bool = False


class TransactionStats(BaseModel):
    """Transaction statistics."""

    count: int
    total_amount: int


class TransactionStatsSummary(BaseModel):
    """Summary of all transaction types."""

    manual: TransactionStats
    crypto: TransactionStats


class DiscountInfo(BaseModel):
    """Discount code information."""

    code: str
    percent: int
    usage: str
    type: str
    expiration: str


class UserProfile(BaseModel):
    """User profile information."""

    id: int
    username: str | None = None
    first_name: str | None = None
    photo_url: str | None = None
    invite: int
    amount: int
    safe: bool
    number: str | None = None
    join_date: str | None = None
    discount: DiscountInfo | None = None
    transactions: TransactionStatsSummary
