"""Normalizing and validating what a user types into the service search."""

from __future__ import annotations

from app.telegram.user.services.search import normalize_service_search_query, validate_service_search_query


def test_normalize_strips_at_sign_and_whitespace_and_converts_persian_digits():
    assert normalize_service_search_query("  @TeSt_۱۲٣  ") == "TeSt_123"
    assert normalize_service_search_query("  ١٢ ٣٤  ") == "1234"


def test_validate_rejects_a_query_that_is_empty_after_normalizing():
    query, error = validate_service_search_query("  @  ")
    assert query is None
    assert "خالی" in error


def test_validate_rejects_a_query_longer_than_128_characters():
    query, error = validate_service_search_query("a" * 129)
    assert query is None
    assert "128" in error
