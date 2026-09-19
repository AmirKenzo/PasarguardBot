"""Normalization helpers for the user-facing service search."""

from __future__ import annotations

PERSIAN_AND_ARABIC_DIGITS = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)

MAX_SERVICE_SEARCH_LENGTH = 128

SERVICE_SEARCH_PROMPT = (
    "🔍 نام کاربری یا کد سرویس را ارسال کنید.\n\n"
    "می‌توانید نام کامل یا بخشی از username را بفرستید.\n"
    "مثال: `ali-vpn` یا `583214`"
)


def normalize_service_search_query(raw: str | None) -> str:
    """Normalize what users commonly paste as a service username or code."""
    query = "".join((raw or "").translate(PERSIAN_AND_ARABIC_DIGITS).split())
    if query.startswith("@"):
        query = query[1:].strip()
    return query


def validate_service_search_query(raw: str | None) -> tuple[str | None, str | None]:
    """Return ``(query, error)`` for a Telegram service-search message."""
    query = normalize_service_search_query(raw)
    if not query:
        return None, "❌ عبارت جست‌وجو خالی است. نام کاربری یا کد سرویس را ارسال کنید."
    if len(query) > MAX_SERVICE_SEARCH_LENGTH:
        return None, f"❌ عبارت جست‌وجو نباید بیشتر از {MAX_SERVICE_SEARCH_LENGTH} کاراکتر باشد."
    return query, None
