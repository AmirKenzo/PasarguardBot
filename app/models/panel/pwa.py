"""Admin panel DTOs: the installable-webapp (PWA) branding form."""

from __future__ import annotations

from pydantic import Field

from app.models.panel.common import ActionResponse, PanelRequest, PanelResponse


class PwaSettingsResponse(PanelResponse):
    app_name: str = ""
    short_name: str = ""
    description: str = ""
    has_custom_icon: bool = False
    icon_version: int = 0


class PwaSettingsSaveRequest(PanelRequest):
    app_name: str = Field("", max_length=45)
    short_name: str = Field("", max_length=12)
    description: str = Field("", max_length=300)


class PwaIconUploadResponse(ActionResponse):
    icon_version: int = 0
