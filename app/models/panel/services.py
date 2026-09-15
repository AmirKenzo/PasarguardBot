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
    """One row from any payment method, normalized to a common shape.

    ``id`` is the raw per-table primary key as a string — unique *within*
    ``source`` but not necessarily across sources, so the frontend keys rows
    on ``f"{source}-{id}"``. Only ``source == "tx"`` rows with
    ``method == "manual_card"`` are ever actionable; everything else confirms
    itself with no admin step.
    """

    id: str
    source: str
    method: str
    user_id: int | None = None
    amount: int = 0
    status: str
    created_at: int | None = None
    has_receipt: bool = False


class PanelTransactionStats(BaseModel):
    pending: int = 0
    approved_7d: int = 0
    rejected_7d: int = 0
    approved_volume_7d: int = 0


class PanelTransactionsRequest(PagedRequest):
    tx_id: str = Field("", description="Filter by the raw per-source id")
    user_id: str = Field("")
    amount: str = Field("")
    method: str = Field("", description="empty | manual_card | crypto")
    status: str = Field("", description="empty | pending | approved | rejected | needs_fix | expired")
    days: int = Field(0, description="0 = all time, else last N days")


class PanelTransactionsResponse(PanelResponse):
    transactions: list[PanelTransactionRow] = Field(default_factory=list)
    meta: PageMeta = Field(default_factory=PageMeta)
    pending_total: int = 0
    stats: PanelTransactionStats = Field(default_factory=PanelTransactionStats)


class PanelTransactionActionRequest(PanelRequest):
    tx_id: int


class PanelReceiptLinkRequest(PanelRequest):
    tx_id: int


class PanelReceiptLinkResponse(PanelResponse):
    url: str | None = None
