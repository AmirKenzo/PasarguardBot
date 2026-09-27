"""WebApp DTOs: phone OTP login, API key login, Telegram init-data session, logout."""

from pydantic import BaseModel, Field

from app.models.webapp.common import ServiceStatus, UserProfile, WebAppAuthRequest


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


class ApiKeyLoginRequest(BaseModel):
    """Log in using a profile-generated API key instead of phone + OTP."""

    api_key: str = Field(..., description="API key issued from the profile page")


class ApiKeyGenerateRequest(WebAppAuthRequest):
    """Generate (or regenerate) the caller's API key. Requires an existing session."""


class ApiKeyGenerateResponse(BaseModel):
    """Response for the API key generate/regenerate endpoint."""

    ok: bool
    api_key: str | None = Field(None, description="Raw key, returned only once at generation time")
    created_at: int | None = None
    error: str | None = None


class WebAppInfoResponse(BaseModel):
    """Response for web app info endpoint."""

    ok: bool
    user: UserProfile | None = None
    services: list[ServiceStatus] | None = None
    error: str | None = None
    session_token: str | None = None
    api_key_login_mode: str = "none"


class WebAppChangeResponse(BaseModel):
    """Response for change operations."""

    ok: bool
    subscription_url: str | None = None
    error: str | None = None
