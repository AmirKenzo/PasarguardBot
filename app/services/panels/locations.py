"""Which locations an invoice lists for a panel.

Each panel picks one of three modes:

* ``auto``   — the panel's nodes, filtered by the plan type's node prefixes (the
  long-standing behaviour, and the default).
* ``manual`` — a list the admin writes for that panel; an empty list falls back
  to the nodes so an invoice never shows a blank line by accident.
* ``hidden`` — no locations line at all.

The manual list is free text typed by an admin (often with flag emoji), so it is
normalised and capped here and only ever rendered as message text — never put in
callback data, where Telegram's 64-byte limit is easy to overflow.
"""

from __future__ import annotations

from pasarguard import PasarguardAPI

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

LOCATIONS_MODE_LABELS: dict[str, str] = {
    LOCATIONS_MODE_AUTO: "خودکار (نودهای پنل)",
    LOCATIONS_MODE_MANUAL: "دستی (لیست خودم)",
    LOCATIONS_MODE_HIDDEN: "مخفی",
}


def panel_locations_mode(panel) -> str:
    mode = str(subscription_settings(panel).get("locations_mode") or LOCATIONS_MODE_AUTO)
    return mode if mode in LOCATIONS_MODES else LOCATIONS_MODE_AUTO


def panel_manual_locations(panel) -> list[str]:
    return parse_locations_value(subscription_settings(panel).get("locations"))


async def fetch_node_locations(panel, plan) -> list[str]:
    """Display names of the panel's nodes that serve this plan; raises if the panel cannot be reached."""
    nodes_stats = await PasarguardAPI(base_url=panel.base_url).get_nodes(token=panel.cookie)
    filtered_nodes = filter_nodes_by_plan_type(nodes_stats.nodes, plan, panel)
    return [format_node_name_for_display(node.name, panel) for node in filtered_nodes if getattr(node, "name", None)]


async def resolve_plan_locations(panel, plan) -> list[str] | None:
    """Locations to list for ``plan`` on ``panel``; ``None`` means hide the line.

    Only the ``auto`` path (and an empty ``manual`` list) talks to the panel, so it
    is the only one that can raise.
    """
    mode = panel_locations_mode(panel)
    if mode == LOCATIONS_MODE_HIDDEN:
        return None
    if mode == LOCATIONS_MODE_MANUAL:
        manual = panel_manual_locations(panel)
        if manual:
            return manual
    return await fetch_node_locations(panel, plan)


def strip_locations_line(template: str) -> str:
    """Drop the line holding ``{locations}`` and the label line right above it."""
    kept: list[str] = []
    for line in template.split("\n"):
        if LOCATIONS_PLACEHOLDER in line:
            if kept and "لوکیشن" in kept[-1] and "{" not in kept[-1]:
                kept.pop()
            continue
        kept.append(line)
    return "\n".join(kept)


def fill_locations(template: str, locations: list[str] | None, *, empty: str = " ") -> str:
    """Put the locations into an invoice template, or remove that part when hidden."""
    if locations is None:
        return strip_locations_line(template)
    return template.replace(LOCATIONS_PLACEHOLDER, LOCATIONS_SEPARATOR.join(locations) or empty)
