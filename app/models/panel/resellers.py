"""Admin panel DTOs: reseller overview, accounts, billing ledger, events, settings and plans."""

from pydantic import BaseModel, Field

from app.models.panel.common import PagedRequest, PageMeta, PanelRequest, PanelResponse
from app.models.panel.plans import BUTTON_STYLE_VALUES
from app.models.panel.services import PanelPanelOption

RESELLER_STATUSES = ("active", "paused", "suspended", "usage_capped", "admin_paused", "expired")


# --------------------------------------------------------------------------- #
#  Overview                                                                     #
# --------------------------------------------------------------------------- #


class PanelResellerRevenue(BaseModel):
    """``payg`` is hourly/usage billing, ``sales`` is purchases, renewals and capacity."""

    payg: int = 0
    sales: int = 0
    total: int = 0


class PanelResellerDayPoint(BaseModel):
    ts: int
    payg: int = 0
    sales: int = 0


class PanelResellerRunwayRow(BaseModel):
    telegram_id: int
    balance: int = 0
    burn_per_hour: int = 0
    hours_left: float | None = None
    accounts: list[str] = Field(default_factory=list)


class PanelResellerExpiringRow(BaseModel):
    code: int
    telegram_id: int
    username: str
    status: str
    expiration_time: int
    purge_at: int | None = Field(None, description="When an expired account is deleted from the panel")


class PanelResellerEventRow(BaseModel):
    id: int
    kind: str
    title: str
    account_code: int | None = None
    telegram_id: int | None = None
    actor_id: int | None = None
    actor_role: str | None = None
    data: dict = Field(default_factory=dict)
    created_at: int


class PanelResellerOverviewResponse(PanelResponse):
    sale_enabled: bool = False
    total: int = 0
    by_status: dict[str, int] = Field(default_factory=dict)
    by_mode: dict[str, int] = Field(default_factory=dict)
    burn_per_hour: int = 0
    revenue_today: PanelResellerRevenue = Field(default_factory=PanelResellerRevenue)
    revenue_7d: PanelResellerRevenue = Field(default_factory=PanelResellerRevenue)
    revenue_30d: PanelResellerRevenue = Field(default_factory=PanelResellerRevenue)
    series: list[PanelResellerDayPoint] = Field(default_factory=list)
    low_runway_hours: int = 6
    at_risk: list[PanelResellerRunwayRow] = Field(default_factory=list)
    expiring: list[PanelResellerExpiringRow] = Field(default_factory=list)
    recent_events: list[PanelResellerEventRow] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
#  Accounts                                                                     #
# --------------------------------------------------------------------------- #


class PanelResellerRow(BaseModel):
    code: int
    telegram_id: int | None = None
    username: str | None = None
    panel_code: int | None = None
    panel: str | None = None
    panel_admin_id: int | None = None
    plan_id: int | None = None
    pricing_mode: str = "fixed"
    purchased_volume: float | None = None
    data_limit: int | None = None
    usage_cap_bytes: int | None = None
    max_users: int | None = None
    createtime: int | None = None
    expiration_time: int | None = None
    status: str = "active"


class PanelResellersRequest(PagedRequest):
    q: str = Field("", max_length=64)
    status: str = Field("", description="empty or one of RESELLER_STATUSES")
    panel_code: int | None = Field(None, ge=1)
    pricing_mode: str = Field("", max_length=20)


class PanelResellersResponse(PanelResponse):
    resellers: list[PanelResellerRow] = Field(default_factory=list)
    panels: list[PanelPanelOption] = Field(default_factory=list)
    statuses: list[str] = Field(default_factory=lambda: list(RESELLER_STATUSES))
    pricing_modes: list[str] = Field(default_factory=list)
    meta: PageMeta = Field(default_factory=PageMeta)


class PanelResellerSnapshotRow(BaseModel):
    """One charge: ``used_bytes`` (usage) or ``billed_minutes`` (hourly) times ``unit_price`` gives ``billed_amount``."""

    id: int
    account_code: int | None = None
    username: str | None = None
    telegram_id: int | None = None
    kind: str = Field("usage", description="hourly | usage")
    used_traffic: int = Field(0, description="Panel's cumulative traffic counter at charge time")
    used_bytes: int | None = Field(None, description="Traffic used in the charged period")
    billed_amount: int = 0
    billed_minutes: int | None = None
    unit_price: float | None = Field(None, description="Rate per GB (usage) or per hour (hourly)")
    rate_estimated: bool = Field(False, description="Rate derived from amount/usage for rows before rates were stored")
    period_start: int | None = None
    snapshot_at: int | None = None
    is_debt: bool = Field(False, description="Charged while the wallet was short; left the balance negative")


class PanelResellerLive(BaseModel):
    """What the panel reports right now; absent when the panel can't be reached."""

    used_traffic: int = 0
    data_limit: int = 0
    total_users: int = 0
    admin_status: str = ""
    login_url: str = ""


class PanelResellerPlanBrief(BaseModel):
    id: int
    pricing_mode: str
    name: str | None = None
    rate: float = 0


class PanelResellerDetailRequest(PanelRequest):
    code: int


class PanelResellerDetailResponse(PanelResponse):
    reseller: PanelResellerRow | None = None
    plan: PanelResellerPlanBrief | None = None
    live: PanelResellerLive | None = None
    live_error: str | None = None
    balance: int | None = None
    billed_total: int | None = None
    runway_hours: float | None = None
    grace_days_left: int | None = None
    actions: list[str] = Field(default_factory=list)
    renew_plans: list[PanelResellerPlanBrief] = Field(default_factory=list)
    snapshots: list[PanelResellerSnapshotRow] = Field(default_factory=list)
    events: list[PanelResellerEventRow] = Field(default_factory=list)
    statuses: list[str] = Field(default_factory=lambda: list(RESELLER_STATUSES))


class PanelResellerUpdateRequest(PanelRequest):
    """Legacy all-in-one edit; ``status`` null leaves the status alone."""

    code: int
    status: str | None = None
    usage_cap_gb: float | None = Field(None, ge=0, description="Null removes the cap")
    max_users: int = Field(0, ge=0)
    extend_days: int = Field(0, ge=0, description="Days added to the current expiry")


class PanelResellerCodeRequest(PanelRequest):
    code: int


PanelResellerDeleteRequest = PanelResellerCodeRequest


class PanelResellerRenewRequest(PanelRequest):
    code: int
    plan_id: int


class PanelResellerExtendRequest(PanelRequest):
    code: int
    days: int = Field(..., ge=1, le=3650)


class PanelResellerUsageCapRequest(PanelRequest):
    code: int
    usage_cap_gb: float | None = Field(None, ge=0, le=1_000_000, description="Null or 0 removes the cap")


class PanelResellerMaxUsersRequest(PanelRequest):
    code: int
    max_users: int = Field(..., ge=0, le=1_000_000)


class PanelResellerPasswordResponse(PanelResponse):
    message: str | None = None
    password: str | None = None


# --------------------------------------------------------------------------- #
#  Ledger and events                                                            #
# --------------------------------------------------------------------------- #


class PanelResellerLedgerRequest(PagedRequest):
    account_code: int | None = None
    telegram_id: int | None = None
    since: int | None = Field(None, ge=0)
    until: int | None = Field(None, ge=0)


class PanelResellerLedgerResponse(PanelResponse):
    rows: list[PanelResellerSnapshotRow] = Field(default_factory=list)
    total_billed: int = 0
    meta: PageMeta = Field(default_factory=PageMeta)


class PanelResellerEventsRequest(PagedRequest):
    account_code: int | None = None
    telegram_id: int | None = None
    kinds: list[str] = Field(default_factory=list, max_length=30)


class PanelResellerEventsResponse(PanelResponse):
    events: list[PanelResellerEventRow] = Field(default_factory=list)
    kinds: list[str] = Field(default_factory=list)
    meta: PageMeta = Field(default_factory=PageMeta)


# --------------------------------------------------------------------------- #
#  Settings                                                                     #
# --------------------------------------------------------------------------- #


class PanelResellerGlobalSettings(BaseModel):
    sale_mode: bool = False
    min_wallet_balance: int = Field(0, ge=0)
    grace_days: int = Field(7, ge=1, le=365)
    low_balance_hours: int = Field(6, ge=1, le=720)
    usage_debt: bool = True


class PanelResellerButtons(BaseModel):
    credentials: bool = True
    change_password: bool = True
    toggle_status: bool = True
    usage_report: bool = True
    usage_cap: bool = True
    buy_user_capacity: bool = True
    delete: bool = True


class PanelResellerPanelSettings(BaseModel):
    code: int
    name: str = ""
    enable: bool = True
    sale_enabled: bool = True
    capacity_enabled: bool = False
    capacity_price_per_user: int = Field(0, ge=0)
    buttons: PanelResellerButtons = Field(default_factory=PanelResellerButtons)


class PanelResellerSettingsResponse(PanelResponse):
    settings: PanelResellerGlobalSettings = Field(default_factory=PanelResellerGlobalSettings)
    panels: list[PanelResellerPanelSettings] = Field(default_factory=list)


class PanelResellerSettingsSaveRequest(PanelRequest):
    """Either part may be left out; ``panels`` only touches the panels it lists."""

    settings: PanelResellerGlobalSettings | None = None
    panels: list[PanelResellerPanelSettings] | None = Field(None, max_length=200)


# --------------------------------------------------------------------------- #
#  Plans                                                                        #
# --------------------------------------------------------------------------- #


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
    data_limit_gb: float = 0
    max_users: int = 0
    duration: int = 0
    role_id: int = 0
    role_name: str | None = None
    enable: bool = True
    display_button_text: str | None = None
    button_style: str | None = None
    button_icon: int | None = None
    linked_accounts: int = 0


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
    data_limit_gb: float | None = Field(None, ge=0, description="Null keeps the stored value; 0 is unlimited")
    max_users: int = Field(0, ge=0)
    duration: int = Field(0, ge=0)
    role_id: int = Field(..., gt=0, description="A role of the Pasarguard panel; its name is read from the panel")
    role_name: str = Field("", max_length=64, description="Ignored; kept for older clients")
    enable: bool = True
    display_button_text: str = Field("", max_length=64)
    button_style: str = Field("", max_length=20)
    button_icon: str = Field("", max_length=64)
    notify_resellers: bool = Field(True, description="Message linked pay-as-you-go resellers when the rate changes")


class PanelResellerPlanDeleteRequest(PanelRequest):
    plan_id: int


class PanelResellerRolesRequest(PanelRequest):
    panel_code: int = Field(..., gt=0)


class PanelResellerRole(BaseModel):
    id: int
    name: str


class PanelResellerRolesResponse(PanelResponse):
    roles: list[PanelResellerRole] = Field(default_factory=list)
