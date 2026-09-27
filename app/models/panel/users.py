"""Admin panel DTOs: bot users."""

from typing import Literal

from pydantic import BaseModel, Field

from app.models.panel.common import ActionResponse, PagedRequest, PageMeta, PanelRequest, PanelResponse

UserState = Literal["active", "banned", "blocked_bot", "deleted"]


class PanelUserRow(BaseModel):
    id: int
    status: str | None = None
    state: UserState = "active"
    number: str | None = None
    balance: int = 0
    joined_at: int | None = None
    services: int = 0


class PanelUsersRequest(PagedRequest):
    q: str = Field("", max_length=64)
    state: str = Field("", description="empty | active | banned | blocked_bot | deleted")
    sort: str = Field("newest", description="newest | oldest")


class PanelUsersResponse(PanelResponse):
    users: list[PanelUserRow] = Field(default_factory=list)
    meta: PageMeta = Field(default_factory=PageMeta)


class PanelUserServiceRow(BaseModel):
    code: int
    username: str | None = None
    panel: str | None = None
    package_size: float | None = None
    expiration_time: int | None = None
    enable: bool = True
    is_test: bool = False


class PanelUserTransactionRow(BaseModel):
    id: int
    amount: int = 0
    status: str | None = None
    created_at: int | None = None


class PanelUserDetailRequest(PanelRequest):
    user_id: int


class PanelUserDetailResponse(PanelResponse):
    user: PanelUserRow | None = None
    services: list[PanelUserServiceRow] = Field(default_factory=list)
    transactions: list[PanelUserTransactionRow] = Field(default_factory=list)
    referrals: int = 0


class PanelUserBalanceRequest(PanelRequest):
    user_id: int
    delta: int = Field(..., description="Signed amount in toman")
    notify: bool = True


class PanelUserBalanceResponse(ActionResponse):
    balance: int | None = None


class PanelUserBlockRequest(PanelRequest):
    user_id: int
    blocked: bool
    notify: bool = True


class PanelUserPhoneRequest(PanelRequest):
    user_id: int
    phone: str = Field(..., max_length=32)


class PanelUserPhoneResponse(ActionResponse):
    """Echoes the stored form, so the page shows what was actually saved."""

    number: str | None = None


class PanelUserMessageRequest(PanelRequest):
    user_id: int
    text: str = Field(..., min_length=1, max_length=4000)


class PanelTransferAdminsRequest(PanelRequest):
    user_id: int
    panel_code: int


class PanelTransferAdminRow(BaseModel):
    username: str
    total_users: int = 0
    status: str | None = None
    note: str | None = None
    suggested: bool = False


class PanelTransferAdminsResponse(PanelResponse):
    current_admin: str | None = None
    admins: list[PanelTransferAdminRow] = Field(default_factory=list)


class PanelTransferPreviewRequest(PanelRequest):
    user_id: int
    panel_code: int
    source_admin: str = Field(..., min_length=1, max_length=64)
    target_admin: str = Field(..., min_length=1, max_length=64)


class PanelTransferConflictRow(BaseModel):
    username: str
    owner_id: int


class PanelTransferPreviewResponse(PanelResponse):
    total_users: int = 0
    status_counts: dict[str, int] = Field(default_factory=dict)
    active_users: int = 0
    will_create: int = 0
    already_linked: int = 0
    conflicts: list[PanelTransferConflictRow] = Field(default_factory=list)
    conflicts_total: int = 0
    active_used_traffic: int = 0
    active_data_limit: int = 0
    active_unlimited: int = 0


class PanelTransferStartRequest(PanelTransferPreviewRequest):
    notify: bool = False


class PanelTransferStartResponse(ActionResponse):
    job_id: str | None = None


class PanelTransferStatusRequest(PanelRequest):
    job_id: str = Field(..., min_length=1, max_length=64)


class PanelTransferResultRow(BaseModel):
    username: str
    panel_user_id: int
    result: str
    reason: str | None = None
    service_code: int | None = None


class PanelTransferStatusResponse(PanelResponse):
    state: str = "running"
    phase: str = "fetch"
    total: int = 0
    processed: int = 0
    skipped_inactive: int = 0
    remaining_active_on_source: int | None = None
    counts: dict[str, int] = Field(default_factory=dict)
    source_admin: str | None = None
    target_admin: str | None = None
    panel_name: str | None = None
    job_error: str | None = None
    rows: list[PanelTransferResultRow] = Field(default_factory=list)
