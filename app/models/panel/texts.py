"""Admin panel DTOs: the editable bot texts."""

from pydantic import BaseModel, Field

from app.models.panel.common import PanelRequest, PanelResponse

BANNER_POSITIONS = ("", "top", "bottom")


class PanelTextEntry(BaseModel):
    """One editable key: its definition plus the stored override, if any."""

    key: str
    title: str | None = None
    placeholders: dict[str, str] = Field(default_factory=dict)
    value: str | None = None
    lang: str | None = None
    banner_url: str | None = None
    banner_position: str | None = None
    stored: bool = False


class PanelTextSection(BaseModel):
    key: str
    name: str | None = None
    icon: str | None = None
    entries: list[PanelTextEntry] = Field(default_factory=list)


class PanelTextsRequest(PanelRequest):
    q: str = Field("", max_length=64)


class PanelTextsResponse(PanelResponse):
    sections: list[PanelTextSection] = Field(default_factory=list)
    banner_positions: list[str] = Field(default_factory=lambda: list(BANNER_POSITIONS))


class PanelTextSaveRequest(PanelRequest):
    key: str = Field(..., min_length=1, max_length=100)
    value: str = Field("", max_length=8192)
    lang: str = Field("", max_length=10)
    banner_url: str = Field("", max_length=500)
    banner_position: str = Field("", max_length=10)


class PanelTextDeleteRequest(PanelRequest):
    key: str = Field(..., min_length=1, max_length=100)
    lang: str = Field("", max_length=10)
