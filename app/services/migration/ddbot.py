"""Adapter for importing DDBot MySQL backups.

DDBot stores Telegram customers in ``user``, Pasarguard connections in
``panel``, and sold accounts in ``subscription``.  The subscription rows do
not carry all of the live Pasarguard fields required by this bot, so this
adapter intentionally supplies only ownership, panel identity, and username
candidates.  The shared migration importer resolves the current status,
numeric panel user id, data limit, and expiry from the live panel before any
rows are committed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from app.services.migration.base import ParsedMigration, ParsedPanel, ParsedService, ParsedUser, SourceAdapter
from app.services.migration.sql_dump import iter_insert_rows

_PASARGUARD_PANEL_TYPE = "pasarguard"


def _as_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _as_amount(value: str | None) -> int:
    """Convert DDBot's DECIMAL wallet value to the integer unit used here."""
    if value is None:
        return 0
    try:
        amount = Decimal(value)
    except InvalidOperation, ValueError:
        return 0
    if not amount.is_finite():
        return 0
    return int(amount)


def _as_timestamp(value: str | None) -> int | None:
    """Parse either a Unix timestamp or a UTC MySQL/ISO timestamp."""
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        pass

    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return int(parsed.timestamp())


def _username_candidates(*values: str | None) -> list[str]:
    """Return non-empty candidates once, preserving source preference order."""
    candidates: list[str] = []
    seen: set[str] = set()
    for value in values:
        candidate = (value or "").strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        candidates.append(candidate)
    return candidates


class DDBotAdapter(SourceAdapter):
    slug = "ddbot"
    display_name = "دی‌دی‌بات (DDBot)"

    def parse(self, sql_text: str) -> ParsedMigration:
        parsed = ParsedMigration(source_slug=self.slug, source_label=self.display_name)
        self._parse_users(sql_text, parsed)
        accepted_panel_ids = self._parse_panels(sql_text, parsed)
        self._parse_services(sql_text, parsed, accepted_panel_ids)
        return parsed

    def _parse_users(self, sql_text: str, parsed: ParsedMigration) -> None:
        for row in iter_insert_rows(sql_text, "user"):
            telegram_id = _as_int(row.get("id"))
            if telegram_id is None:
                continue
            parsed.users.append(
                ParsedUser(
                    telegram_id=telegram_id,
                    amount=_as_amount(row.get("balance")),
                    time_s=_as_timestamp(row.get("created_at")),
                )
            )

    def _parse_panels(self, sql_text: str, parsed: ParsedMigration) -> set[str]:
        accepted_panel_ids: set[str] = set()
        for row in iter_insert_rows(sql_text, "panel"):
            source_id = row.get("id")
            panel_type = (row.get("type") or "").strip().lower()
            name = (row.get("server_name") or "").strip()
            base_url = (row.get("server_url") or "").strip().rstrip("/")
            username = (row.get("server_username") or "").strip()
            password = row.get("server_password") or ""

            if panel_type != _PASARGUARD_PANEL_TYPE or not source_id or not base_url or not username:
                parsed.skipped_panels += 1
                continue

            accepted_panel_ids.add(source_id)
            parsed.panels.append(
                ParsedPanel(
                    source_id=source_id,
                    name=name or f"وارد شده از DDBot #{source_id}",
                    base_url=base_url,
                    username=username,
                    password=password,
                )
            )
        return accepted_panel_ids

    def _parse_services(
        self,
        sql_text: str,
        parsed: ParsedMigration,
        accepted_panel_ids: set[str],
    ) -> None:
        for row in iter_insert_rows(sql_text, "subscription"):
            source_panel_id = row.get("server_id")
            owner_id = _as_int(row.get("user_id"))
            candidates = _username_candidates(row.get("username"), row.get("uuid"))

            if source_panel_id not in accepted_panel_ids or owner_id is None or not candidates:
                parsed.skipped_services += 1
                continue

            parsed.services.append(
                ParsedService(
                    source_panel_id=source_panel_id,
                    owner_id=owner_id,
                    username_candidates=candidates,
                    created_at=_as_timestamp(row.get("insert_date")),
                    enabled=row.get("delete_requested") is None,
                )
            )
