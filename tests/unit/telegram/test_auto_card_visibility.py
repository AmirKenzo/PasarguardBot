from types import SimpleNamespace

import pytest

from app.telegram.admin.settings_payment.texts import is_auto_card_visible


@pytest.mark.parametrize(
    ("enabled", "visibility", "safe", "expected"),
    [
        (False, "all", True, False),
        (True, None, True, True),
        (True, None, False, False),
        (True, "safe_mode", False, False),
        (True, "all", False, True),
    ],
)
def test_is_auto_card_visible(enabled: bool, visibility: str | None, safe: bool, expected: bool) -> None:
    settings = SimpleNamespace(auto_cart=enabled, auto_card_visibility=visibility)
    assert is_auto_card_visible(settings, SimpleNamespace(safe=safe)) is expected


def test_auto_card_hidden_without_settings_or_user() -> None:
    assert is_auto_card_visible(None, SimpleNamespace(safe=True)) is False
    settings = SimpleNamespace(auto_cart=True, auto_card_visibility=None)
    assert is_auto_card_visible(settings, None) is False
