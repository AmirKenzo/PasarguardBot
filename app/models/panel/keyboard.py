"""Admin panel DTOs: the bot keyboard layout, labels, colours and icons."""

from pydantic import BaseModel, Field

from app.models.panel.common import PanelRequest, PanelResponse

# ``none`` clears the built-in default colour; an empty value keeps it.
STYLE_OPTIONS = ("", "primary", "success", "danger", "none")

# Key prefix -> stable section slug, so the client can group and label buttons.
SECTION_PREFIXES: tuple[tuple[str, str], ...] = (
    ("bt.menu_", "main_menu"),
    ("in.ms.", "my_services"),
    ("in.balance.", "balance"),
    ("in.buy.", "buy"),
)
OTHER_SECTION = "other"


class PanelKeyboardButton(BaseModel):
    key: str
    section: str = OTHER_SECTION
    title: str | None = None
    default_text: str | None = None
    text: str | None = None
    style: str | None = None
    default_icon: int | None = None
    icon: int | None = None
    hidden: bool = False
    in_home: bool = False
    # Empty when the button can render; otherwise why the bot holds it back
    # (no_shop_panel, reseller_sale_off, trial_off, setting_off, uptime_disabled).
    blocked: str = ""


class PanelKeyboardResponse(PanelResponse):
    layout: list[list[str]] = Field(default_factory=list)
    buttons: list[PanelKeyboardButton] = Field(default_factory=list)
    home_keys: list[str] = Field(default_factory=list)
    sections: list[str] = Field(default_factory=list)
    style_options: list[str] = Field(default_factory=lambda: list(STYLE_OPTIONS))
    premium_emoji_enabled: bool = False


class PanelKeyboardLayoutRequest(PanelRequest):
    """Rows of button keys, top to bottom. Empty rows are dropped."""

    layout: list[list[str]] = Field(default_factory=list)
    hidden: list[str] = Field(default_factory=list)


class PanelKeyboardButtonSaveRequest(PanelRequest):
    key: str = Field(..., min_length=1, max_length=100)
    text: str = Field("", max_length=100)
    style: str = Field("", max_length=20)
    icon: str = Field("", max_length=64)


class PanelKeyboardIconClearRequest(PanelRequest):
    key: str = Field(..., min_length=1, max_length=100)
