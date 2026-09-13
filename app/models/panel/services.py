"""Admin panel DTOs: sold services and payment transactions."""

from pydantic import BaseModel, Field

from app.models.panel.common import PagedRequest, PageMeta, PanelRequest, PanelResponse


class PanelServiceRow(BaseModel):
    code: int
    user_id: int | None = None
    username: str | None = None
    panel: str | None = None
    panel_code: int | None = None
    package_size: float | None = None
    expiration_time: int | None = None
    enable: bool = True
    expired: bool = False
    is_test: bool = False


class PanelServicesRequest(PagedRequest):
    q: str = Field("", max_length=64)
    panel: str = Field("", description="Panel code, or empty for all")
    state: str = Field("", description="empty | active | expired | test")


class PanelPanelOption(BaseModel):
    code: int
    name: str


class PanelServicesResponse(PanelResponse):
    services: list[PanelServiceRow] = Field(default_factory=list)
    panels: list[PanelPanelOption] = Field(default_factory=list)
    meta: PageMeta = Field(default_factory=PageMeta)


class PanelServiceToggleRequest(PanelRequest):
    code: int
    enabled: bool


class PanelServiceDeleteRequest(PanelRequest):
    code: int


class PanelTransactionRow(BaseModel):
    id: int
    user_id: int | None = None
    amount: int = 0
    status: str | None = None
    method: str | None = None
    created_at: int | None = None
    receipt: str | None = None


class PanelTransactionsRequest(PagedRequest):
    status: str = Field("", description="empty | pending | approved | rejected")
    method: str = Field("", description="empty | card | crypto")


class PanelTransactionsResponse(PanelResponse):
    transactions: list[PanelTransactionRow] = Field(default_factory=list)
    meta: PageMeta = Field(default_factory=PageMeta)
    pending_total: int = 0


class PanelTransactionActionRequest(PanelRequest):
    tx_id: int
