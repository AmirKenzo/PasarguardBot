"""Adapter for importing data from the "wizwiz" bot's MySQL backup.

wizwiz's `orders_list` duplicates the same panel-identity string across three columns
(`remark`, `uuid`, `token`) with no reliable single source of truth for which one the
Pasargard panel actually indexes the config by. Rather than guessing one field, each
service keeps all non-empty candidates and the importer probes the panel with each in
turn (see app.services.migration.importer).
"""

from __future__ import annotations

from app.services.migration.base import ParsedMigration, ParsedPanel, ParsedService, ParsedUser, SourceAdapter
from app.services.migration.sql_dump import iter_insert_rows

_PASARGUARD_PANEL_TYPE = "pasarguard"


def _as_int(value: str | None, default: int | None = None) -> int | None:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


class WizwizAdapter(SourceAdapter):
    slug = "wizwiz"
    display_name = "ویزویز پرو"

    def parse(self, sql_text: str) -> ParsedMigration:
        parsed = ParsedMigration(source_slug=self.slug, source_label=self.display_name)
        self._parse_users(sql_text, parsed)
        accepted_panel_ids = self._parse_panels(sql_text, parsed)
        self._parse_services(sql_text, parsed, accepted_panel_ids)
        return parsed

    def _parse_users(self, sql_text: str, parsed: ParsedMigration) -> None:
        for row in iter_insert_rows(sql_text, "users"):
            telegram_id = _as_int(row.get("userid"))
            if telegram_id is None:
                continue
            parsed.users.append(
                ParsedUser(
                    telegram_id=telegram_id,
                    amount=_as_int(row.get("wallet"), 0) or 0,
                    time_s=_as_int(row.get("date")),
                )
            )

    def _parse_panels(self, sql_text: str, parsed: ParsedMigration) -> set[str]:
        accepted_panel_ids: set[str] = set()
        for row in iter_insert_rows(sql_text, "server_config"):
            source_id = row.get("id")
            panel_type = (row.get("type") or "").strip().lower()
            base_url = (row.get("panel_url") or "").strip().rstrip("/")
            username = (row.get("username") or "").strip()
            password = row.get("password") or ""

            if panel_type != _PASARGUARD_PANEL_TYPE or not source_id or not base_url or not username:
                parsed.skipped_panels += 1
                continue

            accepted_panel_ids.add(source_id)
            parsed.panels.append(
                ParsedPanel(
                    source_id=source_id,
                    name=f"وارد شده از ویزویز پرو #{source_id}",
                    base_url=base_url,
                    username=username,
                    password=password,
                )
            )
        return accepted_panel_ids

    def _parse_services(self, sql_text: str, parsed: ParsedMigration, accepted_panel_ids: set[str]) -> None:
        for row in iter_insert_rows(sql_text, "orders_list"):
            server_id = row.get("server_id")
            owner_id = _as_int(row.get("userid"))
            candidates = [v.strip() for v in (row.get("remark"), row.get("uuid"), row.get("token")) if v and v.strip()]

            if server_id not in accepted_panel_ids or owner_id is None or not candidates:
                parsed.skipped_services += 1
                continue

            parsed.services.append(
                ParsedService(
                    source_panel_id=server_id,
                    owner_id=owner_id,
                    username_candidates=candidates,
                    created_at=_as_int(row.get("date")),
                    enabled=(row.get("status") or "0").strip() == "1",
                )
            )
