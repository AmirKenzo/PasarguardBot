"""Admin panel DTOs: the PasarGuard panels the bot sells from."""

from pydantic import BaseModel, Field

from app.models.panel.common import ActionResponse, PanelRequest, PanelResponse

AUTH_TYPES = ("password", "api_key")
BUTTON_STYLES = ("primary", "success", "danger", "")


class PanelRow(BaseModel):
    code: int
    name: str
    base_url: str
    tunnel_url: str | None = None
    username: str | None = None
    auth_type: str = "password"
    enable: bool = True
    test_enabled: bool = False
    test_volume_gb: float = 2.0
    test_duration_days: int = 3


class PanelListResponse(PanelResponse):
    panels: list[PanelRow] = Field(default_factory=list)
    auth_types: list[str] = Field(default_factory=lambda: list(AUTH_TYPES))


class PanelSaveRequest(PanelRequest):
    """Create when ``code`` is null, otherwise update that panel.

    ``secret`` holds the panel password or the API key. On update an empty
    value means "keep the stored credential".
    """

    code: int | None = None
    name: str = Field(..., min_length=1, max_length=50)
    base_url: str = Field(..., min_length=4, max_length=255)
    tunnel_url: str = Field("", max_length=255)
    auth_type: str = "password"
    username: str = Field("", max_length=50)
    secret: str = Field("", max_length=512)
    enable: bool = True
    test_enabled: bool = False
    test_volume_gb: float = Field(2.0, ge=0)
    test_duration_days: int = Field(3, ge=0)


class PanelCodeRequest(PanelRequest):
    code: int


class PanelTestResponse(ActionResponse):
    latency_ms: float | None = None


class PanelButtonSettingsPayload(BaseModel):
    time: bool | None = None
    volume: bool | None = None
    renew: bool | None = None
    change_subscription: bool | None = None
    other_links: bool | None = None
    change_link: bool | None = None
    copy_link: bool | None = None
    qr: bool | None = None
    transfer: bool | None = None
    clients: bool | None = None
    usage_chart: bool | None = None
    info: bool | None = None
    delete_service: bool | None = None


class PanelSubscriptionSettingsPayload(BaseModel):
    default_group_ids: list[int] | None = None
    user_limit: int | None = None
    display_mode: str | None = None
    node_prefixes: list[str] | None = None
    show_prefixes_in_locations: bool | None = None
    link_mode: str | None = None
    single_config_link_indexes: str | None = None
    admin_login_path: str | None = None


class PanelTrialSettingsPayload(BaseModel):
    enabled: bool | None = None
    volume_gb: float | None = None
    duration_days: int | None = None


class PanelRenewalSettingsPayload(BaseModel):
    auto_renew_enabled: bool | None = None
    webhook_notifications_enabled: bool | None = None
    renew_volume_remaining_mode: bool | None = None


class PanelSalesSettingsPayload(BaseModel):
    shop_enabled: bool | None = None
    reseller_enabled: bool | None = None


class PanelCustomBuySettingsPayload(BaseModel):
    enabled: bool | None = None
    price_per_gb: int | None = None
    price_per_day: int | None = None
    min_gb: float | None = None
    max_gb: float | None = None
    min_days: int | None = None
    max_days: int | None = None
    ip_limit: int | None = None


class PanelResellerCapacitySettingsPayload(BaseModel):
    enabled: bool | None = None
    price_per_user: int | None = None


class PanelResellerButtonSettingsPayload(BaseModel):
    credentials: bool | None = None
    change_password: bool | None = None
    toggle_status: bool | None = None
    usage_report: bool | None = None
    usage_cap: bool | None = None
    buy_user_capacity: bool | None = None
    delete: bool | None = None


class PanelSettingsResponse(PanelResponse):
    code: int
    buttons: PanelButtonSettingsPayload = Field(default_factory=PanelButtonSettingsPayload)
    subscription: PanelSubscriptionSettingsPayload = Field(default_factory=PanelSubscriptionSettingsPayload)
    trial: PanelTrialSettingsPayload = Field(default_factory=PanelTrialSettingsPayload)
    renewal: PanelRenewalSettingsPayload = Field(default_factory=PanelRenewalSettingsPayload)
    sales: PanelSalesSettingsPayload = Field(default_factory=PanelSalesSettingsPayload)
    custom_buy: PanelCustomBuySettingsPayload = Field(default_factory=PanelCustomBuySettingsPayload)
    reseller_capacity: PanelResellerCapacitySettingsPayload = Field(
        default_factory=PanelResellerCapacitySettingsPayload
    )
    reseller_buttons: PanelResellerButtonSettingsPayload = Field(default_factory=PanelResellerButtonSettingsPayload)


class PanelSettingsSaveRequest(PanelRequest):
    code: int
    buttons: PanelButtonSettingsPayload | None = None
    subscription: PanelSubscriptionSettingsPayload | None = None
    trial: PanelTrialSettingsPayload | None = None
    renewal: PanelRenewalSettingsPayload | None = None
    sales: PanelSalesSettingsPayload | None = None
    custom_buy: PanelCustomBuySettingsPayload | None = None
    reseller_capacity: PanelResellerCapacitySettingsPayload | None = None
    reseller_buttons: PanelResellerButtonSettingsPayload | None = None


class PanelStatusResponse(PanelResponse):
    code: int
    name: str = ""
    enable: bool = True
    shop_enabled: bool = True
    reseller_enabled: bool = True
    auth_type: str = "password"
    base_url: str = ""
    tunnel_url: str | None = None

    status_error: str | None = None
    version: str | None = None
    mem_total: float | None = None
    mem_used: float | None = None
    cpu_cores: int | None = None
    cpu_usage: float | None = None
    total_user: int | None = None
    online_users: int | None = None
    active_users: int | None = None
    on_hold_users: int | None = None
    disabled_users: int | None = None
    expired_users: int | None = None
    limited_users: int | None = None
    incoming_bandwidth: int | None = None
    outgoing_bandwidth: int | None = None


class PanelGroupOption(BaseModel):
    id: int
    name: str


class PanelGroupsResponse(PanelResponse):
    groups: list[PanelGroupOption] = Field(default_factory=list)


class PanelButtonStyleResponse(PanelResponse):
    text: str = ""
    style: str = ""
    icon_id: str | None = None


class PanelButtonStyleSaveRequest(PanelRequest):
    code: int
    text: str | None = None
    style: str | None = Field(None, description="One of primary/success/danger/'' (none)")
    icon_id: str | None = Field(None, description="Digits only; empty/omitted leaves the icon untouched")
    clear_icon: bool = False
