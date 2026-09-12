"""WebApp DTOs: login, OTP, session, logout, web account management."""

from pydantic import BaseModel, Field

from app.models.webapp.common import ServiceStatus, UserProfile


class WebAppLoginRequest(BaseModel):
    """Login request for web app."""

    username: str = Field(..., description="Username for login")
    password: str = Field(..., description="Password for login")


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


class WebAccountCreateRequest(BaseModel):
    """Request to create web account."""

    username: str = Field(..., description="Username for web account")
    password: str = Field(..., description="Password for web account")
    session_token: str | None = Field(None, description="Session token from login")


class WebAccountCreateResponse(BaseModel):
    """Response for web account creation."""

    ok: bool
    message: str
    error: str | None = None


class WebAccountChangePasswordRequest(BaseModel):
    """Request to change web account password."""

    new_password: str = Field(..., description="New password")
    session_token: str | None = Field(None, description="Session token from login")


class WebAccountChangePasswordResponse(BaseModel):
    """Response for password change."""

    ok: bool
    message: str
    error: str | None = None


class WebRegistrationModeRequest(BaseModel):
    """Request to change registration mode."""

    mode: str = Field(..., description="Registration mode: all, customers, none")


class WebRegistrationModeResponse(BaseModel):
    """Response for registration mode change."""

    ok: bool
    message: str
    error: str | None = None
