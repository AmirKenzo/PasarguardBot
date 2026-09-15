"""Admin panel DTOs: the bot settings form."""

from typing import Any

from pydantic import BaseModel, Field

from app.models.panel.common import PanelRequest, PanelResponse


class PanelSettingField(BaseModel):
    """One setting, described well enough for the client to render it."""

    key: str
    type: str = Field("number", description="bool | number | text | select")
    default: Any = None
    value: Any = None
    options: list[str] | None = None
    read_only: bool = False


class PanelSettingSection(BaseModel):
    key: str
    fields: list[PanelSettingField] = Field(default_factory=list)


class PanelSettingsResponse(PanelResponse):
    sections: list[PanelSettingSection] = Field(default_factory=list)
    initialized: bool = True


class PanelSettingsSaveRequest(PanelRequest):
    """Only keys present in the section defaults are written; the rest are dropped."""

    values: dict[str, Any] = Field(default_factory=dict)
