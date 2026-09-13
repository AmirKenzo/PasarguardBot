"""WebApp DTOs: unified payment transaction history."""

from pydantic import BaseModel, Field


class WebAppTransactionItem(BaseModel):
    id: str
    type_key: str
    currency: str | None = None
    amount: int
    status: str
    created_at: int
    emoji: str


class WebAppTransactionsRequest(BaseModel):
    session_token: str | None = Field(None, description="Session token from login")
    init_data: str | None = Field(None, description="Telegram init data")
    page: int = Field(1, ge=1)
    limit: int = Field(10, ge=1, le=50)


class WebAppTransactionsResponse(BaseModel):
    ok: bool
    transactions: list[WebAppTransactionItem] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    limit: int = 10
    total_pages: int = 0
    error: str | None = None
