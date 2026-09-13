"""Shared DTOs for the admin panel API."""

from pydantic import BaseModel, Field


class PanelRequest(BaseModel):
    """Every panel call carries the same credentials as the WebApp calls."""

    session_token: str | None = Field(None, description="Session token from the WebApp login")
    init_data: str | None = Field(None, description="Telegram WebApp init data")


class PagedRequest(PanelRequest):
    page: int = Field(1, ge=1)
    limit: int = Field(25, ge=1, le=100)


class PanelResponse(BaseModel):
    ok: bool = True
    error: str | None = None


class PageMeta(BaseModel):
    total: int = 0
    page: int = 1
    limit: int = 25
    total_pages: int = 0


def page_meta(total: int, page: int, limit: int) -> PageMeta:
    limit = max(1, limit)
    return PageMeta(
        total=total,
        page=page,
        limit=limit,
        total_pages=(total + limit - 1) // limit,
    )


class ActionResponse(PanelResponse):
    """Result of a state-changing call."""

    message: str | None = None
