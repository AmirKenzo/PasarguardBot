"""Admin panel DTOs: join-lock channels and log destinations."""

from pydantic import BaseModel, Field

from app.models.panel.common import PanelRequest, PanelResponse

DESTINATION_TYPES = ("channel", "supergroup")


class PanelChannelRow(BaseModel):
    id: int
    title: str | None = None
    link: str | None = None


class PanelLogChannelRow(BaseModel):
    id: int
    log_type: str
    chat_id: int | None = None
    topic_id: int | None = None
    destination_type: str = "channel"
    is_active: bool = True


class PanelChannelsResponse(PanelResponse):
    channels: list[PanelChannelRow] = Field(default_factory=list)
    log_channels: list[PanelLogChannelRow] = Field(default_factory=list)
    log_types: list[str] = Field(default_factory=list)
    destination_types: list[str] = Field(default_factory=lambda: list(DESTINATION_TYPES))


class PanelChannelCreateRequest(PanelRequest):
    channel_id: int
    title: str = Field(..., min_length=1, max_length=100)
    link: str = Field(..., min_length=1, max_length=100)


class PanelChannelDeleteRequest(PanelRequest):
    channel_id: int


class PanelLogChannelSaveRequest(PanelRequest):
    log_type: str
    destination_type: str = "channel"
    chat_id: int
    topic_id: int | None = None


class PanelLogChannelDeleteRequest(PanelRequest):
    log_id: int
