"""Shared types for bot-to-bot data migration adapters."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ParsedUser:
    telegram_id: int
    amount: int = 0
    time_s: int | None = None


@dataclass(slots=True)
class ParsedPanel:
    source_id: str
    name: str
    base_url: str
    username: str
    password: str


@dataclass(slots=True)
class ParsedService:
    source_panel_id: str
    owner_id: int
    username_candidates: list[str]
    created_at: int | None = None
    # Whether the source bot's own bookkeeping still marks this row active — only a
    # pre-filter to skip obviously-dead rows before spending a panel API call on them.
    # Actual expiry/data-limit/enabled state always comes live from the panel.
    enabled: bool = True


@dataclass(slots=True)
class ParsedMigration:
    source_slug: str
    source_label: str
    users: list[ParsedUser] = field(default_factory=list)
    panels: list[ParsedPanel] = field(default_factory=list)
    services: list[ParsedService] = field(default_factory=list)
    skipped_panels: int = 0
    skipped_services: int = 0


class SourceAdapter:
    """Parses one source bot's .sql backup into a ParsedMigration."""

    slug: str
    display_name: str

    def parse(self, sql_text: str) -> ParsedMigration:
        raise NotImplementedError
