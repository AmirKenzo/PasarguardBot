"""Admin panel DTOs: crypto wallets, manual cards and auto-approve rules."""

from pydantic import BaseModel, Field

from app.models.panel.common import PanelRequest, PanelResponse

WALLET_TYPES = ("TRX", "USDT", "USDT-TON", "USDT-BEP20", "TON", "POL")


class PanelWalletRow(BaseModel):
    id: int
    type: str
    address: str
    has_api_key: bool = False


class PanelCardRow(BaseModel):
    id: int
    number: str
    name: str
    active: bool = False


class PanelAutoApproveRuleRow(BaseModel):
    id: int
    min_successful_tx: int = 0
    max_successful_tx: int | None = None
    auto_approve_delay_minutes: int = 0
    is_active: bool = False


class PanelPaymentsResponse(PanelResponse):
    wallets: list[PanelWalletRow] = Field(default_factory=list)
    available_wallet_types: list[str] = Field(default_factory=list)
    cards: list[PanelCardRow] = Field(default_factory=list)
    rules: list[PanelAutoApproveRuleRow] = Field(default_factory=list)


class PanelWalletCreateRequest(PanelRequest):
    wallet_type: str
    address: str = Field(..., min_length=4, max_length=128)
    api_key: str = Field("", max_length=128)


class PanelWalletDeleteRequest(PanelRequest):
    wallet_id: int


class PanelCardCreateRequest(PanelRequest):
    number: str = Field(..., min_length=12, max_length=32)
    name: str = Field(..., min_length=1, max_length=64)
    active: bool = False


class PanelCardActionRequest(PanelRequest):
    card_id: int


class PanelRuleCreateRequest(PanelRequest):
    min_successful_tx: int = Field(0, ge=0)
    max_successful_tx: int | None = Field(None, ge=0)
    auto_approve_delay_minutes: int = Field(30, ge=0)


class PanelRuleToggleRequest(PanelRequest):
    rule_id: int
    is_active: bool


class PanelRuleDeleteRequest(PanelRequest):
    rule_id: int


class PanelTonPaysStats(BaseModel):
    paid_today: int = 0
    amount_today: int = 0
    open_invoices: int = 0
    failed_today: int = 0


class PanelTonPaysResponse(PanelResponse):
    enabled: bool = False
    mode: str = "standard"
    api_key_masked: str = ""
    custom_key_masked: str = ""
    has_api_key: bool = False
    has_custom_key: bool = False
    ready: bool = False
    deposit_min: int = 0
    deposit_max: int = 0
    bonus_enabled: bool = False
    bonus_percent: int = 0
    webhook_url: str | None = None
    stats: PanelTonPaysStats = Field(default_factory=PanelTonPaysStats)


class PanelTonPaysSaveRequest(PanelRequest):
    """Empty key fields keep the stored key; `clear_*` removes it."""

    enabled: bool | None = None
    mode: str | None = Field(None, pattern="^(standard|custom)$")
    api_key: str = Field("", max_length=256)
    custom_key: str = Field("", max_length=256)
    clear_api_key: bool = False
    clear_custom_key: bool = False
    deposit_min: int | None = Field(None, ge=0)
    deposit_max: int | None = Field(None, ge=0)
    bonus_enabled: bool | None = None
    bonus_percent: int | None = Field(None, ge=0, le=100)


class PanelTonPaysTestRequest(PanelRequest):
    """Test the given key, or the stored key for `mode` when `api_key` is empty."""

    mode: str = Field("standard", pattern="^(standard|custom)$")
    api_key: str = Field("", max_length=256)


class PanelIrGatewayStats(BaseModel):
    paid_today: int = 0
    amount_today: int = 0
    open_payments: int = 0
    failed_today: int = 0


class PanelIrGatewayRow(BaseModel):
    key: str
    title: str
    enabled: bool = False
    sandbox: bool = True
    ready: bool = False
    has_merchant: bool = False
    merchant_masked: str = ""
    merchant_pattern: str = ""
    merchant_hint: str = ""
    sandbox_hint: str = ""
    deposit_min: int = 0
    deposit_max: int = 0
    bonus_enabled: bool = False
    bonus_percent: int = 0
    callback_url: str | None = None
    stats: PanelIrGatewayStats = Field(default_factory=PanelIrGatewayStats)


class PanelIrGatewaysResponse(PanelResponse):
    gateways: list[PanelIrGatewayRow] = Field(default_factory=list)


class PanelIrGatewaySaveRequest(PanelRequest):
    """An empty merchant keeps the stored one; `clear_merchant` removes it."""

    gateway: str = Field(..., min_length=1, max_length=20)
    enabled: bool | None = None
    sandbox: bool | None = None
    merchant_id: str = Field("", max_length=64)
    clear_merchant: bool = False
    deposit_min: int | None = Field(None, ge=1000)
    deposit_max: int | None = Field(None, ge=1000)
    bonus_enabled: bool | None = None
    bonus_percent: int | None = Field(None, ge=0, le=100)


class PanelIrGatewayTestRequest(PanelRequest):
    """Test the given merchant, or the stored one when `merchant_id` is empty."""

    gateway: str = Field(..., min_length=1, max_length=20)
    sandbox: bool = True
    merchant_id: str = Field("", max_length=64)
