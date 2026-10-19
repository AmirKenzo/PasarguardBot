"""Admin panel DTOs: web app color themes (custom library, active theme, user options)."""

from typing import Any

from pydantic import BaseModel, Field

from app.models.panel.common import PanelRequest, PanelResponse


class WebappThemeEntry(BaseModel):
    id: int
    name: str
    source_bot: str = ""
    imported: bool = False
    created_at: int
    updated_at: int
    theme: dict[str, Any]


class WebappThemeOverviewResponse(PanelResponse):
    mode: str = "telegram"
    active: str = "default"
    user_scheme: bool = True
    user_pick: bool = False
    themes: list[WebappThemeEntry] = Field(default_factory=list)
    max_themes: int = 0


class WebappThemeIdRequest(PanelRequest):
    theme_id: int


class WebappThemeSaveRequest(PanelRequest):
    """A new theme (no ``theme_id``) or an edit of a library theme."""

    theme_id: int | None = None
    name: str = Field("", max_length=100)
    theme: dict[str, Any]
    source_bot: str = Field("", max_length=40)
    imported: bool = False


class WebappThemeSaveResponse(PanelResponse):
    message: str | None = None
    theme_id: int | None = None


class WebappThemeActivateRequest(PanelRequest):
    """``active`` is "custom:<id>" for a library theme or a preset id with its palette in ``theme``."""

    active: str = Field(..., max_length=60)
    theme: dict[str, Any] | None = None


class WebappThemeOptionsRequest(PanelRequest):
    mode: str | None = None
    user_scheme: bool | None = None
    user_pick: bool | None = None


class WebappThemeShareResponse(PanelResponse):
    data: dict[str, Any] = Field(default_factory=dict)
    file_name: str = ""
