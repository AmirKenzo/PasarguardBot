"""Admin panel DTOs: theme packs (shareable bot texts, button labels and home layout)."""

from typing import Any

from pydantic import BaseModel, Field

from app.models.panel.common import PanelRequest, PanelResponse

MAX_SELECTION = 2000


class ThemePackTextInfo(BaseModel):
    """A text that can go into a pack, with the languages it is customized in."""

    key: str
    title: str
    section: str
    langs: list[str] = Field(default_factory=list)
    has_default: bool = False
    has_banner: bool = False
    # Kinds of personal data the stored text seems to carry (username, link, card_number, phone).
    hints: list[str] = Field(default_factory=list)


class ThemePackButtonInfo(BaseModel):
    key: str
    title: str
    section: str
    customized: bool = False
    has_icon: bool = False
    hints: list[str] = Field(default_factory=list)


class ThemePackSection(BaseModel):
    key: str
    name: str = ""
    icon: str = ""


class ThemePackImportInfo(BaseModel):
    id: int
    pack_name: str = ""
    pack_id: int | None = None
    mode: str = "merge"
    created_at: int
    restored: bool = False
    summary: dict[str, Any] = Field(default_factory=dict)


class ThemePackLibraryEntry(BaseModel):
    id: int
    name: str
    source_bot: str = ""
    created_at: int
    updated_at: int
    counts: dict[str, int] = Field(default_factory=dict)
    active: bool = False


class ThemePackOverviewResponse(PanelResponse):
    packs: list[ThemePackLibraryEntry] = Field(default_factory=list)
    texts: list[ThemePackTextInfo] = Field(default_factory=list)
    buttons: list[ThemePackButtonInfo] = Field(default_factory=list)
    text_sections: list[ThemePackSection] = Field(default_factory=list)
    button_sections: list[str] = Field(default_factory=list)
    layout_customized: bool = False
    last_import: ThemePackImportInfo | None = None


class ThemePackCreateRequest(PanelRequest):
    """Save the bot's current look (the selected part of it) as a new library pack."""

    name: str = Field("", max_length=100)
    text_keys: list[str] = Field(default_factory=list, max_length=MAX_SELECTION)
    button_keys: list[str] = Field(default_factory=list, max_length=MAX_SELECTION)
    include_layout: bool = False
    include_banners: bool = True
    include_icons: bool = True
    include_defaults: bool = False


class ThemePackIdRequest(PanelRequest):
    pack_id: int = Field(..., ge=1)


class ThemePackSaveRequest(PanelRequest):
    """Store pack data in the library: a new pack (no id) or the edited version of one."""

    pack_id: int | None = Field(None, ge=1)
    name: str = Field("", max_length=100)
    pack: dict[str, Any] = Field(default_factory=dict)
    # The editor saves strictly (nothing invalid is accepted); a file import drops what this bot cannot use.
    strict: bool = False


class ThemePackItem(BaseModel):
    id: str
    kind: str
    key: str
    lang: str | None = None
    title: str = ""
    section: str = ""
    status: str
    current: str | None = None
    incoming: str | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class ThemePackSaveResponse(PanelResponse):
    message: str | None = None
    pack_id: int | None = None
    dropped: list[ThemePackItem] = Field(default_factory=list)


class ThemePackDetailResponse(PanelResponse):
    pack: ThemePackLibraryEntry | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    file_name: str = ""


class ThemePackPreviewRequest(PanelRequest):
    """Compare a pack with the bot: either a library pack or pack data from a file."""

    pack_id: int | None = Field(None, ge=1)
    pack: dict[str, Any] | None = None


class ThemePackPreviewResponse(PanelResponse):
    name: str = ""
    source: dict[str, Any] = Field(default_factory=dict)
    items: list[ThemePackItem] = Field(default_factory=list)


class ThemePackApplyRequest(ThemePackPreviewRequest):
    # None applies every entry that differs from the bot (a one-click switch).
    item_ids: list[str] | None = Field(None, max_length=MAX_SELECTION)
    mode: str = Field("merge", max_length=10)


class ThemePackApplyResponse(PanelResponse):
    message: str | None = None
    applied: int = 0
    reset: int = 0
    import_id: int | None = None


class ThemePackCurrentRequest(PanelRequest):
    """The bot's current values for some keys, as pack entries (the editor adds them to a pack)."""

    text_keys: list[str] = Field(default_factory=list, max_length=MAX_SELECTION)
    button_keys: list[str] = Field(default_factory=list, max_length=MAX_SELECTION)
    include_layout: bool = False
