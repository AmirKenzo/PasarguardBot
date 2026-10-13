"""
Request and Response models for router endpoints.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator


# Webhook Models (aligned with PasarGuard UserNotificationResponse / AdminDetails)
class UserNotificationEnable(BaseModel):
    """User-scoped notification toggles from PasarGuard."""

    create: bool = True
    modify: bool = True
    delete: bool = True
    status_change: bool = True
    reset_data_usage: bool = True
    data_reset_by_next: bool = True
    subscription_revoked: bool = True


NotificationSettings = UserNotificationEnable


class AdminBase(BaseModel):
    id: int | None = None
    username: str

    model_config = ConfigDict(extra="ignore")


class AdminContactInfo(AdminBase):
    """Admin contact info embedded in user.webhook payloads."""

    telegram_id: int | None = None
    discord_webhook: str | None = None
    sub_domain: str | None = None
    profile_title: str | None = None
    support_url: str | None = None
    notification_enable: UserNotificationEnable | None = None

    model_config = ConfigDict(extra="ignore")

    @field_validator("notification_enable", mode="before")
    @classmethod
    def convert_notification_enable(cls, value):
        if value is None or isinstance(value, UserNotificationEnable):
            return value
        if isinstance(value, dict):
            return UserNotificationEnable(**value)
        return value


UserAdminInfo = AdminContactInfo


class AdminRoleData(BaseModel):
    id: int | None = None
    name: str = ""
    is_owner: bool = False

    model_config = ConfigDict(extra="ignore")


class AdminDetails(AdminContactInfo):
    """Full admin payload for webhook 'by' field."""

    total_users: int = 0
    used_traffic: int = 0
    data_limit: int | None = None
    status: str = "active"
    sub_template: str | None = None
    lifetime_used_traffic: int | None = None
    note: str | None = None
    role: AdminRoleData | None = None
    is_disabled: bool | None = None
    is_limited: bool | None = None
    is_sudo: bool | None = None  # legacy Marzban field

    model_config = ConfigDict(extra="ignore")

    @field_validator("used_traffic", "lifetime_used_traffic", mode="before")
    @classmethod
    def cast_to_int(cls, v):
        if v is None:
            return v
        return int(v)


AdminInfo = AdminDetails


class NextPlanModel(BaseModel):
    user_template_id: int | None = None
    data_limit: int | None = None
    expire: int | None = None
    add_remaining_traffic: bool = False

    model_config = ConfigDict(extra="ignore")


class VmessSettings(BaseModel):
    id: str = ""

    model_config = ConfigDict(extra="ignore")


class VlessSettings(BaseModel):
    id: str = ""
    flow: str = ""

    model_config = ConfigDict(extra="ignore")


class TrojanSettings(BaseModel):
    password: str = ""

    model_config = ConfigDict(extra="ignore")


class ShadowsocksSettings(BaseModel):
    password: str = ""
    method: str = "chacha20-ietf-poly1305"

    model_config = ConfigDict(extra="ignore")


class WireGuardSettings(BaseModel):
    private_key: str | None = None
    public_key: str | None = None
    peer_ips: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="ignore")


class HysteriaSettings(BaseModel):
    auth: str = ""

    model_config = ConfigDict(extra="ignore")


class ProxySettings(BaseModel):
    vmess: VmessSettings | None = None
    vless: VlessSettings | None = None
    trojan: TrojanSettings | None = None
    shadowsocks: ShadowsocksSettings | None = None
    wireguard: WireGuardSettings | None = None
    hysteria: HysteriaSettings | None = None

    model_config = ConfigDict(extra="ignore")


class UserInfo(BaseModel):
    """User payload from PasarGuard UserNotificationResponse."""

    proxy_settings: ProxySettings = Field(default_factory=ProxySettings)
    expire: str | int | None = None
    data_limit: int | None = None
    data_limit_reset_strategy: str | None = None
    note: str | None = None
    on_hold_expire_duration: int | None = None
    on_hold_timeout: str | int | None = None
    group_ids: list[int] | None = Field(default_factory=list)
    auto_delete_in_days: int | None = None
    hwid_limit: int | None = None
    next_plan: NextPlanModel | None = None
    id: int
    username: str
    status: str
    used_traffic: int = 0
    lifetime_used_traffic: int = 0
    created_at: str | None = None
    edit_at: str | None = None
    online_at: str | None = None
    subscription_url: str = ""
    admin: AdminContactInfo | None = None
    group_names: list[str] | None = Field(default_factory=list)

    model_config = ConfigDict(extra="ignore")

    @field_validator("used_traffic", "lifetime_used_traffic", "data_limit", mode="before")
    @classmethod
    def cast_to_int(cls, v):
        if v is None:
            return v
        return int(v)


class WebhookEvent(BaseModel):
    """Complete PasarGuard webhook event."""

    enqueued_at: float
    send_at: float
    tries: int = 0
    username: str
    action: str = Field(..., description="Event action type")
    by: AdminDetails | None = None
    user: UserInfo | None = None
    days_left: int | None = Field(None, description="Days remaining")
    used_percent: float | None = Field(None, description="Usage percentage")
    reason: str | None = Field(None, description="Disable reason")

    model_config = ConfigDict(extra="ignore")


class WebhookResponse(BaseModel):
    """Webhook response."""

    ok: bool = True
    message: str = "Webhook received"
