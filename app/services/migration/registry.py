"""Registry of available source-bot migration adapters.

Adding support for another source bot (ddbot, mirza, ...) is one new adapter module
plus one entry here — nothing else in the migration engine or the admin UI needs to change.
"""

from __future__ import annotations

from app.services.migration.base import SourceAdapter
from app.services.migration.faoxima import FaoximaAdapter
from app.services.migration.wizwiz import WizwizAdapter

ADAPTERS: dict[str, SourceAdapter] = {adapter.slug: adapter for adapter in (WizwizAdapter(), FaoximaAdapter())}
