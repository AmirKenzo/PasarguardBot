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
