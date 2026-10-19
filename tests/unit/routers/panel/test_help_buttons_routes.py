"""Admin panel help buttons: row grouping, target validation, callback keys, release matching and save rules."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.models.panel.help_buttons import (
    PanelHelpButtonSaveRequest,
    PanelHelpLayoutRequest,
    PanelHelpReleaseRequest,
    PanelHelpTarget,
)
from app.routers.panel import guard, help_buttons
from app.routers.panel.auth import PanelActor


@pytest.fixture(autouse=True)
def actor(monkeypatch):
    async def authenticate(**kwargs):
        return PanelActor(user_id=111111111, ip="127.0.0.1")

    async def no_audit(**kwargs):
        return None

    monkeypatch.setattr(guard, "authenticate_admin", authenticate)
    monkeypatch.setattr(help_buttons.audit, "record", no_audit)


def _btn(id_: int, number: int, **fields) -> SimpleNamespace:
    base = {
        "id": id_,
        "button_number": number,
        "button_text": f"b{id_}",
        "button_url": None,
        "button_style": None,
        "button_icon": None,
        "callback_key": None,
        "repo_owner": None,
        "repo_name": None,
        "categories": None,
        "download_targets": None,
        "ios_url": None,
        "custom_message": None,
    }
    base.update(fields)
    return SimpleNamespace(**base)


def test_layout_groups_consecutive_numbers_like_the_bot() -> None:
    buttons = [_btn(1, 1), _btn(2, 3), _btn(3, 4), _btn(4, 10)]
    assert help_buttons._layout_of(buttons) == [[1], [2, 3], [4]]


def test_kind_is_derived_from_stored_fields() -> None:
    assert help_buttons._kind(_btn(1, 1, button_url="https://t.me/x")) == "link"
    assert help_buttons._kind(_btn(2, 2, callback_key="v2rayng", repo_owner="2dust", repo_name="v2rayNG")) == "app"
    assert help_buttons._kind(_btn(3, 3, callback_key="faq", custom_message="hi")) == "text"


def test_legacy_categories_are_flagged_and_exposed_as_targets() -> None:
    app = _btn(
        5, 5, callback_key="v2rayng", repo_owner="2dust", repo_name="v2rayNG", categories={"Android": ["universal.apk"]}
    )
    out = help_buttons._button_out(app)
    assert out.legacy_categories is True
    assert out.repo == "2dust/v2rayNG"
    assert [t.patterns for t in out.targets] == [["universal.apk"]]


def test_clean_targets_rejects_missing_text_and_patterns() -> None:
    assert isinstance(help_buttons._clean_targets([PanelHelpTarget(button_text="", patterns=["a"])]), str)
    assert isinstance(help_buttons._clean_targets([PanelHelpTarget(button_text="x", patterns=["  "])]), str)


def test_clean_targets_keeps_ids_and_replaces_duplicates() -> None:
    cleaned = help_buttons._clean_targets(
        [
            PanelHelpTarget(id="abc123", button_text="A", button_style="none", patterns=[" a.apk ", ""]),
            PanelHelpTarget(id="abc123", button_text="B", button_style="success", patterns=["b.apk"]),
        ]
    )
    assert not isinstance(cleaned, str)
    assert cleaned[0]["id"] == "abc123"
    assert cleaned[0]["patterns"] == ["a.apk"]
    assert cleaned[0]["button_style"] is None
    assert cleaned[1]["id"] != "abc123"
    assert cleaned[1]["button_style"] == "success"


async def test_callback_key_is_ascii_without_underscores(monkeypatch) -> None:
    taken = {"v2rayng"}

    class Crud:
        async def get_by_callback_key(self, key):
            return object() if key in taken else None

    monkeypatch.setattr(help_buttons, "HelpDownloadAppCRUD", Crud)
    key = await help_buttons._new_callback_key("V2ray NG_beta")
    assert key == "v2rayngbeta"
    key = await help_buttons._new_callback_key("v2ray_ng")
    assert key.startswith("v2rayng") and key != "v2rayng"
    persian = await help_buttons._new_callback_key("برنامه")
    assert persian.isascii() and "_" not in persian and persian


async def test_release_matching_uses_bot_patterns(monkeypatch) -> None:
    help_buttons._release_cache.clear()

    async def fetch(owner, name):
        assert (owner, name) == ("2dust", "v2rayNG")
        return "1.9.46", [
            {"name": "v2rayNG_1.9.46_universal.apk", "size": 1048576},
            {"name": "v2rayNG_1.9.46_arm64-v8a.apk", "size": 0},
            {"name": "notes.txt", "size": 0},
        ]

    monkeypatch.setattr(help_buttons, "fetch_latest_release_assets", fetch)
    payload = PanelHelpReleaseRequest(
        repo="https://github.com/2dust/v2rayNG/",
        targets=[
            PanelHelpTarget(id="uni", button_text="U", patterns=["v2rayNG_%.%.%_universal.apk"]),
            PanelHelpTarget(id="all", button_text="A", patterns=["v2rayNG_%.%.%_%.apk"]),
        ],
    )
    result = await help_buttons.help_release_files(payload, None)
    assert result.ok and result.tag == "1.9.46"
    owners = {f.name: f.target_id for f in result.files}
    assert owners["v2rayNG_1.9.46_universal.apk"] == "uni"
    assert owners["v2rayNG_1.9.46_arm64-v8a.apk"] == "all"
    assert owners["notes.txt"] is None
    assert result.matches == {"uni": 1, "all": 2}
    assert result.files[0].size_mb == 1.0


async def test_release_rejects_bad_repo() -> None:
    result = await help_buttons.help_release_files(PanelHelpReleaseRequest(repo="not a repo"), None)
    assert result.ok is False


async def test_link_save_validates_url(monkeypatch) -> None:
    payload = PanelHelpButtonSaveRequest(kind="link", text="Guide", url="ftp://x")
    result = await help_buttons.save_help_button(payload, None)
    assert result.ok is False


async def test_link_save_normalizes_tme_and_opens_new_row(monkeypatch) -> None:
    calls = {}

    class Links:
        async def next_row_number(self):
            return 7

        async def set_button(self, number, **fields):
            calls["number"] = number
            calls.update(fields)
            return True

        async def get_button(self, number):
            return SimpleNamespace(id=42)

    monkeypatch.setattr(help_buttons, "HelpButtonCRUD", Links)
    payload = PanelHelpButtonSaveRequest(kind="link", text=" Guide ", url="t.me/channel", style="success")
    result = await help_buttons.save_help_button(payload, None)
    assert result.ok and result.id == 42
    assert calls["number"] == 7
    assert calls["button_url"] == "https://t.me/channel"
    assert calls["button_text"] == "Guide"
    assert calls["button_style"] == "success"
    assert calls["clear_icon"] is True


async def test_kind_change_is_refused(monkeypatch) -> None:
    class Links:
        async def get_by_id(self, id_):
            return _btn(id_, 1, button_url="https://t.me/x")

    monkeypatch.setattr(help_buttons, "HelpButtonCRUD", Links)
    payload = PanelHelpButtonSaveRequest(id=1, kind="text", text="x", custom_message="hello")
    result = await help_buttons.save_help_button(payload, None)
    assert result.ok is False


async def test_layout_rejects_overfull_rows() -> None:
    result = await help_buttons.save_help_layout(PanelHelpLayoutRequest(layout=[list(range(1, 10))]), None)
    assert result.ok is False
