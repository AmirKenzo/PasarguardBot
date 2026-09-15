"""Admin panel DTOs: the PasarGuard panels the bot sells from."""

from pydantic import BaseModel, Field

from app.models.panel.common import PanelRequest, PanelResponse

AUTH_TYPES = ("password", "api_key")


class PanelRow(BaseModel):
    code: int
    name: str
    base_url: str
    tunnel_url: str | None = None
    username: str | None = None
    auth_type: str = "password"
    enable: bool = True
    test_enabled: bool = False
    test_volume_gb: float = 2.0
    test_duration_days: int = 3


class PanelListResponse(PanelResponse):
    panels: list[PanelRow] = Field(default_factory=list)
    auth_types: list[str] = Field(default_factory=lambda: list(AUTH_TYPES))


class PanelSaveRequest(PanelRequest):
    """Create when ``code`` is null, otherwise update that panel.

    ``secret`` holds the panel password or the API key. On update an empty
    value means "keep the stored credential".
    """

    code: int | None = None
    name: str = Field(..., min_length=1, max_length=50)
    base_url: str = Field(..., min_length=4, max_length=255)
    tunnel_url: str = Field("", max_length=255)
    auth_type: str = "password"
    username: str = Field("", max_length=50)
    secret: str = Field("", max_length=512)
    enable: bool = True
    test_enabled: bool = False
    test_volume_gb: float = Field(2.0, ge=0)
    test_duration_days: int = Field(3, ge=0)


class PanelCodeRequest(PanelRequest):
    code: int
