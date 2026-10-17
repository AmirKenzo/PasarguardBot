"""Admin panel DTOs: the bot's help menu buttons, download apps and their stored release files."""

from typing import Literal

from pydantic import BaseModel, Field

from app.models.panel.common import ActionResponse, EmojiId, PanelRequest, PanelResponse

HelpButtonKind = Literal["link", "app", "text"]
HELP_STYLE_OPTIONS = ("none", "primary", "success", "danger")


class PanelHelpTarget(BaseModel):
    """One download button of an app: the files it sends are picked by name patterns."""

    id: str = Field("", max_length=40)
    button_text: str = Field("", max_length=64)
    button_style: str | None = Field(None, max_length=20)
    button_icon: str | None = Field(None, max_length=64)
    patterns: list[str] = Field(default_factory=list, max_length=30)


class PanelHelpButton(BaseModel):
    id: int
    number: int
    kind: HelpButtonKind
    text: str = ""
    style: str | None = None
    icon: EmojiId | None = None
    url: str | None = None
    callback_key: str | None = None
    repo: str | None = None
    ios_url: str | None = None
    targets: list[PanelHelpTarget] = Field(default_factory=list)
    legacy_categories: bool = False
    custom_message: str | None = None


class PanelHelpPreset(BaseModel):
    key: str
    name: str
    repo: str


class PanelHelpSync(BaseModel):
    """State of the "download latest releases into the log channel" run."""

    running: bool = False
    last_summary: str | None = None
    log_channel_set: bool = False


class PanelHelpButtonsResponse(PanelResponse):
    buttons: list[PanelHelpButton] = Field(default_factory=list)
    layout: list[list[int]] = Field(default_factory=list)
    presets: list[PanelHelpPreset] = Field(default_factory=list)
    sync: PanelHelpSync = Field(default_factory=PanelHelpSync)
    premium_emoji_enabled: bool = False


class PanelHelpLayoutRequest(PanelRequest):
    layout: list[list[int]] = Field(default_factory=list, max_length=200)


class PanelHelpButtonSaveRequest(PanelRequest):
    id: int | None = None
    kind: HelpButtonKind
    text: str = Field(..., min_length=1, max_length=64)
    style: str = Field("none", max_length=20)
    icon: str = Field("", max_length=64)
    url: str = Field("", max_length=500)
    repo: str = Field("", max_length=241)
    ios_url: str = Field("", max_length=500)
    targets: list[PanelHelpTarget] = Field(default_factory=list, max_length=20)
    custom_message: str = Field("", max_length=4000)


class PanelHelpButtonSaveResponse(ActionResponse):
    id: int | None = None


class PanelHelpButtonIdRequest(PanelRequest):
    id: int


class PanelHelpPresetsRequest(PanelRequest):
    keys: list[str] = Field(default_factory=list, max_length=20)


class PanelHelpReleaseRequest(PanelRequest):
    repo: str = Field(..., min_length=3, max_length=241)
    targets: list[PanelHelpTarget] = Field(default_factory=list, max_length=20)
    refresh: bool = False


class PanelHelpReleaseFile(BaseModel):
    name: str
    size_mb: float = 0
    target_id: str | None = None


class PanelHelpReleaseResponse(PanelResponse):
    tag: str = ""
    files: list[PanelHelpReleaseFile] = Field(default_factory=list)
    matches: dict[str, int] = Field(default_factory=dict)


class PanelHelpVersion(BaseModel):
    tag: str
    count: int
    files: list[str] = Field(default_factory=list)


class PanelHelpVersionsResponse(PanelResponse):
    versions: list[PanelHelpVersion] = Field(default_factory=list)


class PanelHelpVersionDeleteRequest(PanelRequest):
    id: int
    tag: str = Field("", max_length=120)
