"""Adapter for importing data from the "Faoxima" bot's MySQL backup.

Faoxima's `invoice` table has no working foreign key to `marzban_panel` (its
`source_panel_code` column is unpopulated in practice) — the only usable link is
matching `invoice.Service_location` against `marzban_panel.name_panel` as free text.
If that name is not unique across panels, a service naming it cannot be attributed to
one panel reliably, so such names are treated as unresolvable rather than guessed.
"""

from __future__ import annotations

from app.services.migration.base import ParsedMigration, ParsedPanel, ParsedService, ParsedUser, SourceAdapter
from app.services.migration.sql_dump import iter_insert_rows

_ACTIVE_STATUS = "active"


def _as_int(value: str | None, default: int | None = None) -> int | None:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


class FaoximaAdapter(SourceAdapter):
    slug = "faoxima"
    display_name = "فاکسیما"

    def parse(self, sql_text: str) -> ParsedMigration:
        parsed = ParsedMigration(source_slug=self.slug, source_label=self.display_name)
        self._parse_users(sql_text, parsed)
        panel_id_by_name = self._parse_panels(sql_text, parsed)
        self._parse_services(sql_text, parsed, panel_id_by_name)
        return parsed

    def _parse_users(self, sql_text: str, parsed: ParsedMigration) -> None:
        for row in iter_insert_rows(sql_text, "user"):
            telegram_id = _as_int(row.get("id"))
            if telegram_id is None:
                continue
            parsed.users.append(ParsedUser(telegram_id=telegram_id, amount=_as_int(row.get("Balance"), 0) or 0))

    def _parse_panels(self, sql_text: str, parsed: ParsedMigration) -> dict[str, str]:
        """Returns {normalized name_panel: source_id} for panels with a unique name."""
        name_to_id: dict[str, str] = {}
        ambiguous_names: set[str] = set()

        for row in iter_insert_rows(sql_text, "marzban_panel"):
            source_id = row.get("id")
            name = (row.get("name_panel") or "").strip()
            base_url = (row.get("url_panel") or "").strip().rstrip("/")
            username = (row.get("username_panel") or "").strip()
            password = row.get("password_panel") or ""

            if not source_id or not base_url or not username:
                parsed.skipped_panels += 1
                continue

            parsed.panels.append(
                ParsedPanel(
                    source_id=source_id,
                    name=name or f"وارد شده از فاکسیما #{source_id}",
                    base_url=base_url,
                    username=username,
                    password=password,
                )
            )

            if name:
                if name in name_to_id and name_to_id[name] != source_id:
                    ambiguous_names.add(name)
                else:
                    name_to_id[name] = source_id

        for name in ambiguous_names:
            name_to_id.pop(name, None)
        return name_to_id

    def _parse_services(self, sql_text: str, parsed: ParsedMigration, panel_id_by_name: dict[str, str]) -> None:
        for row in iter_insert_rows(sql_text, "invoice"):
            status = (row.get("Status") or "").strip().lower()
            owner_id = _as_int(row.get("id_user"))
            location = (row.get("Service_location") or "").strip()
            source_panel_id = panel_id_by_name.get(location)
            candidates = [v.strip() for v in (row.get("username"), row.get("uuid")) if v and v.strip()]

            if status != _ACTIVE_STATUS or owner_id is None or source_panel_id is None or not candidates:
                parsed.skipped_services += 1
                continue

            parsed.services.append(
                ParsedService(
                    source_panel_id=source_panel_id,
                    owner_id=owner_id,
                    username_candidates=candidates,
                    created_at=_as_int(row.get("time_sell")),
                    enabled=True,
                )
            )
