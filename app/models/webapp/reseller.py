"""Reseller (Pasarguard panel admin) purchase and management from the web app.

Every value is raw (bytes, unix timestamps, Toman integers); the frontend formats them.
"""

from typing import Literal

from pydantic import BaseModel, Field

from app.models.webapp.common import WebAppAuthRequest


class WebAppResellerResponse(BaseModel):
    ok: bool = True
    error: str | None = None


# --------------------------------------------------------------------------- #
#  Buy                                                                          #
# --------------------------------------------------------------------------- #


class ResellerPlanFeatures(BaseModel):
    """What a buyer of the plan gets; add-on prices are 0 when the add-on is off (plan or panel toggle)."""

    renewable: bool = False
    expires: bool = False
    unlimited_volume: bool = False
    usage_cap: bool = False
    needs_wallet: bool = False
    extra_day_price: int = 0
    extra_gb_price: int = Field(0, description="Price of one extra GB")
    extra_user_price: int = 0


class ResellerPlanItem(BaseModel):
    id: int
    pricing_mode: str
    name: str | None = None
    price: int = 0
    unit_price: int = 0
    min_volume: float = 0
    max_volume: float = 0
    volume_step: float = 1
    data_limit_bytes: int = 0
    max_users: int = 0
    duration_days: int = 0
    needs_volume: bool = False
    needs_wallet: bool = False
    features: ResellerPlanFeatures = Field(default_factory=ResellerPlanFeatures)


class ResellerPanelItem(BaseModel):
    code: int
    name: str
    plans: list[ResellerPlanItem] = Field(default_factory=list)


class WebAppResellerBuyOptionsResponse(WebAppResellerResponse):
    """``enabled`` is False when reseller sales are off or no panel has a plan; the buy card is then hidden."""

    enabled: bool = False
    min_wallet_balance: int = 0
    grace_days: int = Field(0, description="Days an expired reseller is kept before it is purged")
    balance: int = 0
    panels: list[ResellerPanelItem] = Field(default_factory=list)


class WebAppResellerUsernameRequest(WebAppAuthRequest):
    panel_code: int


class WebAppResellerUsernameResponse(WebAppResellerResponse):
    username: str | None = None


class WebAppResellerBuyRequest(WebAppAuthRequest):
    panel_code: int
    plan_id: int
    username: str = Field(..., max_length=32)
    volume: float | None = Field(None, gt=0, le=1_000_000, allow_inf_nan=False)
    discount_code: str | None = Field(None, max_length=64)


class WebAppResellerBuyPreviewResponse(WebAppResellerResponse):
    panel_name: str | None = None
    plan: ResellerPlanItem | None = None
    username: str | None = None
    volume: float | None = None
    base_price: int = 0
    final_price: int = 0
    discount_percent: int = 0
    balance: int = 0
    balance_after: int = 0
    can_pay: bool = False
    wallet_error: str | None = Field(None, description="Minimum wallet rule for hourly/usage plans")


class WebAppResellerBuyConfirmResponse(WebAppResellerResponse):
    account_code: int | None = None
    panel_url: str | None = None
    username: str | None = None
    password: str | None = None
    amount_paid: int = 0
    new_balance: int | None = None


# --------------------------------------------------------------------------- #
#  Accounts                                                                     #
# --------------------------------------------------------------------------- #


class ResellerAccountItem(BaseModel):
    code: int
    username: str
    panel_name: str | None = None
    pricing_mode: str
    status: str
    expiration_timestamp: int | None = None
    max_users: int = 0
    created_timestamp: int | None = None
    extra_users: int = 0


class WebAppResellerAccountsResponse(WebAppResellerResponse):
    accounts: list[ResellerAccountItem] = Field(default_factory=list)
    balance: int = 0
    burn_per_hour: int = 0
    runway_hours: float | None = None
    can_buy: bool = False


class WebAppResellerCodeRequest(WebAppAuthRequest):
    code: int


class ResellerRenewPlanItem(BaseModel):
    id: int
    name: str | None = None
    price: int = 0
    data_limit_bytes: int = 0
    duration_days: int = 0
    pricing_mode: str | None = None
    max_users: int = 0
    enabled: bool = True


class ResellerEventItem(BaseModel):
    id: int
    kind: str
    title: str
    data: dict = Field(default_factory=dict)
    created_at: int


class WebAppResellerAccountResponse(WebAppResellerResponse):
    account: ResellerAccountItem | None = None
    panel_url: str | None = None
    actions: list[str] = Field(default_factory=list)
    admin_locked: bool = False
    live: bool = Field(True, description="False when the panel could not be reached")
    used_traffic_bytes: int = 0
    data_limit_bytes: int = 0
    total_users: int = 0
    usage_cap_bytes: int | None = None
    purchased_volume: float | None = None
    rate: float = 0
    balance: int | None = None
    billed_total: int | None = None
    runway_hours: float | None = None
    grace_days_left: int | None = None
    renew_plans: list[ResellerRenewPlanItem] = Field(
        default_factory=list, description="Only the account's own plan; renewal never switches plans"
    )
    capacity_price_per_user: int = 0
    capacity_presets: list[int] = Field(default_factory=list)
    events: list[ResellerEventItem] = Field(default_factory=list)
    plan: ResellerPlanItem | None = None
    features: ResellerPlanFeatures | None = None
    plan_max_users: int = Field(0, description="User limit of the plan itself; 0 = unlimited")
    extra_users: int = Field(0, description="User slots bought on top of the plan limit")
    grace_days: int = 0
    min_wallet_balance: int = 0
    addon_presets: dict[str, list[int]] = Field(default_factory=dict)
    addon_max_quantity: dict[str, int] = Field(default_factory=dict)


class WebAppResellerPasswordResponse(WebAppResellerResponse):
    password: str | None = None
    message: str | None = None


class WebAppResellerActionResponse(WebAppResellerResponse):
    message: str | None = None
    new_balance: int | None = None


class WebAppResellerRenewRequest(WebAppAuthRequest):
    code: int
    plan_id: int
    discount_code: str | None = Field(None, max_length=64)


class WebAppResellerRenewPreviewResponse(WebAppResellerResponse):
    plan: ResellerRenewPlanItem | None = None
    base_price: int = 0
    final_price: int = 0
    discount_percent: int = 0
    balance: int = 0
    can_pay: bool = False
    balance_after: int = 0
    expiry_before: int | None = None
    expiry_after: int | None = None
    data_limit_before: int = Field(0, description="Bytes; 0 = unlimited")
    data_limit_after: int = 0
    max_users: int = Field(0, description="Unchanged by renewal; 0 = unlimited")


class WebAppResellerUsageCapRequest(WebAppAuthRequest):
    code: int
    usage_cap_gb: float | None = Field(None, ge=0, le=1_000_000, description="Null or 0 removes the cap")


class WebAppResellerCapacityRequest(WebAppAuthRequest):
    code: int
    quantity: int = Field(..., ge=1, le=10_000)


class WebAppResellerCapacityPreviewResponse(WebAppResellerResponse):
    price_per_user: int = 0
    total_price: int = 0
    limit_before: int = 0
    limit_after: int = 0
    balance: int = 0
    can_pay: bool = False


AddonKind = Literal["extra_days", "extra_volume", "buy_user_capacity"]


class WebAppResellerAddonRequest(WebAppAuthRequest):
    """``quantity`` is days, GB or user slots depending on ``addon``."""

    code: int
    addon: AddonKind
    quantity: int = Field(..., ge=1, le=100_000)


class WebAppResellerAddonPreviewResponse(WebAppResellerResponse):
    """``before``/``after``: expiry timestamp (days), bytes (volume) or user count (users)."""

    addon: str | None = None
    quantity: int = 0
    unit_price: int = 0
    total: int = 0
    before: int = 0
    after: int = 0
    balance: int = 0
    balance_after: int = 0
    can_pay: bool = False


class WebAppResellerPageRequest(WebAppAuthRequest):
    code: int
    page: int = Field(1, ge=1)
    limit: int = Field(20, ge=1, le=50)


class ResellerUsageRow(BaseModel):
    """``used_bytes`` (usage) or ``billed_minutes`` (hourly) times ``unit_price`` gives ``amount``."""

    snapshot_at: int
    period_start: int | None = None
    kind: str = Field("usage", description="hourly | usage")
    used_bytes: int = 0
    billed_minutes: int | None = None
    unit_price: float | None = None
    rate_estimated: bool = False
    amount: int = 0
    is_debt: bool = False


class WebAppResellerUsageResponse(WebAppResellerResponse):
    rows: list[ResellerUsageRow] = Field(default_factory=list)
    total_billed: int = 0
    has_more: bool = False


class WebAppResellerEventsResponse(WebAppResellerResponse):
    events: list[ResellerEventItem] = Field(default_factory=list)
    total: int = 0
