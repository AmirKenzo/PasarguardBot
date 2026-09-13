"""Admin panel DTOs: crypto wallets, manual cards and auto-approve rules."""

from pydantic import BaseModel, Field

from app.models.panel.common import PanelRequest, PanelResponse

WALLET_TYPES = ("TRX", "USDT", "TON")


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
