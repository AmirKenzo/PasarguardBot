"""Which panels currently hand out a free trial.

A trial used to be a single panel code on the settings row, so a shop with a
normal panel and a premium one could only advertise one of them. The choice now
lives on each panel next to the trial volume and duration it already carried.

The old setting is still honoured: an install that never touched the new switch
keeps offering the trial it was configured with, and starts offering more the
moment a second panel is switched on.
"""

from __future__ import annotations

from typing import Any

from app.db.crud.panels import PanelsManager
from app.db.crud.settings import SettingsManager
from app.services.panels.settings import panel_test_enabled


async def trial_panels(setting: Any | None = None) -> list[Any]:
    """Every enabled panel offering a trial, in the order they were added."""
    if setting is None:
        setting = await SettingsManager().get_settings()

    panels = await PanelsManager().get_all_panels()
    chosen = [panel for panel in panels if panel_test_enabled(panel)]
    if chosen:
        return chosen

    legacy_code = int(getattr(setting, "test_panel_id", 0) or 0)
    if not legacy_code:
        return []
    return [panel for panel in panels if int(panel.code) == legacy_code and panel.enable]


async def trial_offered(setting: Any | None = None) -> bool:
    """Whether the trial button has anywhere to send a user."""
    if setting is None:
        setting = await SettingsManager().get_settings()
    if not (setting and setting.test_mode):
        return False
    return bool(await trial_panels(setting))
