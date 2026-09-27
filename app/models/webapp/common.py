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
    """Service status information.

    Webapp-only model (the Telegram bot has its own separate message formatting),
    so every value here is raw (bytes, unix timestamps, plain numbers) rather than
    pre-formatted text -- the frontend formats everything itself so it can render
    either Persian or English depending on the user's selected language.
    """

    code: str
    username: str
    panel_name: str | None = None
    status: str | None = None
    used_traffic_bytes: int = 0
    remaining_traffic_bytes: int = 0
    total_traffic_bytes: int = 0
    expiration_timestamp: int | None = None
    subscription_url: str | None = None
    ip_limit: int | None = None
    helper_subscription_url: str | None = None
    config_value: int | None = None
    lifetime_used_traffic: int | None = None
    last_connection: int | None = None
    last_edit: int | None = None
    reset_strategy: str | None = None
    total_possible_traffic: int | None = None
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
    """Discount code information (raw fields -- the webapp frontend formats
    usage/type/expiration itself for bilingual display)."""

    code: str
    percent: int
    times_used: int
    usage_limit: int
    is_public: bool
    expiration_timestamp: int | None = None


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
    join_date: int | None = None
    discount: DiscountInfo | None = None
    transactions: TransactionStatsSummary
    has_api_key: bool = False
    api_key_created_at: int | None = None
