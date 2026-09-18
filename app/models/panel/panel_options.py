from pydantic import BaseModel, Field

from app.models.panel.common import PagedRequest, PageMeta, PanelResponse

PANEL_OPTION_FIELDS = ("code", "name", "enable", "base_url")
DEFAULT_PANEL_OPTION_FIELDS = ("code", "name")


class PanelOptionsRequest(PagedRequest):
    q: str = Field("", max_length=64)
    fields: list[str] = Field(default_factory=lambda: list(DEFAULT_PANEL_OPTION_FIELDS))


class PanelOptionRow(BaseModel):
    code: int
    name: str | None = None
    enable: bool | None = None
    base_url: str | None = None


class PanelOptionsResponse(PanelResponse):
    panels: list[PanelOptionRow] = Field(default_factory=list)
    meta: PageMeta = Field(default_factory=PageMeta)
