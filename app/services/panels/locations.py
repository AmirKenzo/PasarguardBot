"""Which locations an invoice lists for a panel.

Each panel picks a mode:

* ``auto``   — the panel's nodes, filtered by the plan type's node prefixes (the
  long-standing behaviour, and the default).
* ``manual`` — a text the admin writes for that panel, placed on the invoice
  exactly as sent: it replaces the template's whole locations section, label
  included, so the admin decides the wording and layout. An empty text falls
  back to the nodes so an invoice never shows a blank section by accident.
* ``hidden`` — no locations section at all.

The manual text lives in the bot texts table (key ``panel_locations_<code>``),
not on the panel row: bot texts keep the bot's markdown, so premium custom emoji
(``[🇩🇪](emoji/<id>)``) survive from the admin's message to the invoice. It is
only ever rendered as message text — never put in callback data, where
Telegram's 64-byte limit is easy to overflow with flag emoji.
"""

from __future__ import annotations

from dataclasses import dataclass

from pasarguard import PasarguardAPI

from app import Kenzo
from app.db.crud.bot_texts import BotTextCRUD, panel_locations_text_key
from app.services.panels.nodes import filter_nodes_by_plan_type, format_node_name_for_display
from app.services.panels.settings import (
    LOCATIONS_MODE_AUTO,
    LOCATIONS_MODE_HIDDEN,
    LOCATIONS_MODE_MANUAL,
    LOCATIONS_MODES,
    parse_locations_value,
    subscription_settings,
)

LOCATIONS_SEPARATOR = " ⌁ "
LOCATIONS_PLACEHOLDER = "{locations}"
LOCATIONS_TEXT_LANG = "fa"
LOCATIONS_TEXT_MAX_LENGTH = 3000

LOCATIONS_MODE_LABELS: dict[str, str] = {
    LOCATIONS_MODE_AUTO: "خودکار (نودهای پنل)",
    LOCATIONS_MODE_MANUAL: "دستی (متن خودم)",
    LOCATIONS_MODE_HIDDEN: "مخفی",
}


@dataclass(frozen=True)
class LocationsBlock:
    text: str
    custom: bool = False


def panel_locations_mode(panel) -> str:
    mode = str(subscription_settings(panel).get("locations_mode") or LOCATIONS_MODE_AUTO)
    return mode if mode in LOCATIONS_MODES else LOCATIONS_MODE_AUTO


def plain_location(text: str) -> str:
    """Text as a reader sees it: premium-emoji and other markdown stripped."""
    try:
        plain, _entities = Kenzo.parse_mode.parse(text)
    except Exception:
        return text
    return plain.strip()


def validate_locations_text(text: str) -> str | None:
    """Return why ``text`` cannot be saved as a panel's locations, or None when it is fine."""
    if not text.strip():
        return "متن خالی است."
    if len(text) > LOCATIONS_TEXT_MAX_LENGTH:
        return f"متن طولانی است (حداکثر {LOCATIONS_TEXT_MAX_LENGTH} کاراکتر)."
    return None


async def get_manual_locations_text(panel) -> str:
    """The stored text exactly as the admin wrote it; panels saved before the move fall back to their own field."""
    text = await BotTextCRUD().get_text(key=panel_locations_text_key(panel.code))
    if text is not None:
        return text
    return "\n".join(parse_locations_value(subscription_settings(panel).get("locations")))


async def save_manual_locations_text(panel_code: int, text: str) -> bool:
    """Store the text as sent (an empty text clears it). Callers validate first."""
    key = panel_locations_text_key(panel_code)
    if not text.strip():
        await BotTextCRUD().delete_text(key=key)
        return True
    return await BotTextCRUD().set_text(key=key, value=text.strip(), lang=LOCATIONS_TEXT_LANG)


async def fetch_node_locations(panel, plan) -> list[str]:
    """Display names of the panel's nodes that serve this plan; raises if the panel cannot be reached."""
    nodes_stats = await PasarguardAPI(base_url=panel.base_url).get_nodes(token=panel.cookie)
    filtered_nodes = filter_nodes_by_plan_type(nodes_stats.nodes, plan, panel)
    return [format_node_name_for_display(node.name, panel) for node in filtered_nodes if getattr(node, "name", None)]


async def resolve_plan_locations(panel, plan) -> LocationsBlock | None:
    """The locations for ``plan`` on ``panel``; ``None`` means hide the section.

    Only the node path talks to the panel, so it is the only one that can raise.
    """
    mode = panel_locations_mode(panel)
    if mode == LOCATIONS_MODE_HIDDEN:
        return None
    if mode == LOCATIONS_MODE_MANUAL:
        manual = (await get_manual_locations_text(panel)).strip()
        if manual:
            return LocationsBlock(manual, custom=True)
    return LocationsBlock(LOCATIONS_SEPARATOR.join(await fetch_node_locations(panel, plan)))


def location_lines(block: LocationsBlock | None) -> list[str]:
    """Plain, non-empty lines of a locations block, for places that cannot render markdown."""
    if block is None:
        return []
    return [line.strip() for line in plain_location(block.text).split("\n") if line.strip()]


def replace_locations_section(template: str, replacement: str | None) -> str:
    """Swap the template's locations section — the ``{locations}`` line and the
    label line right above it — for ``replacement``, or drop it when ``None``."""
    kept: list[str] = []
    for line in template.split("\n"):
        if LOCATIONS_PLACEHOLDER in line:
            if kept and "لوکیشن" in kept[-1] and "{" not in kept[-1]:
                kept.pop()
            if replacement is not None:
                kept.append(replacement)
            continue
        kept.append(line)
    return "\n".join(kept)


def fill_locations(template: str, block: LocationsBlock | None, *, empty: str = " ") -> str:
    """Put the locations into an invoice template.

    Hidden removes the section; an admin-written text replaces the whole section
    (it carries its own label and layout); node names only fill ``{locations}``.
    """
    if block is None:
        return replace_locations_section(template, None)
    if block.custom:
        return replace_locations_section(template, block.text)
    return template.replace(LOCATIONS_PLACEHOLDER, block.text or empty)
