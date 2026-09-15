"""WebApp DTOs: phone OTP login, Telegram init-data session, logout."""

from pydantic import BaseModel, Field

from app.models.webapp.common import ServiceStatus, UserProfile


class PhoneLoginStartRequest(BaseModel):
    """Start phone login by requesting OTP."""

    phone: str = Field(..., description="User phone number")


class PhoneLoginVerifyRequest(BaseModel):
    """Verify OTP sent to Telegram and return session."""

    phone: str = Field(..., description="User phone number")
    code: str = Field(..., description="One-time code")


class LogoutRequest(BaseModel):
    """Request model for logout operation."""

    session_token: str = Field(..., description="Session token to revoke")


class WebAppInfoResponse(BaseModel):
    """Response for web app info endpoint."""

    ok: bool
    user: UserProfile | None = None
    services: list[ServiceStatus] | None = None
    error: str | None = None
    session_token: str | None = None


class WebAppChangeResponse(BaseModel):
    """Response for change operations."""

    ok: bool
    subscription_url: str | None = None
    error: str | None = None
