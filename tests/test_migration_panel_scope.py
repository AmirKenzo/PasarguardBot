from types import SimpleNamespace

from app.db.crud.services import ServiceCRUD
from app.services.migration import importer
from app.services.migration.base import ParsedPanel, ParsedService


def _source_panel() -> ParsedPanel:
    return ParsedPanel(
        source_id="source-panel",
        name="Source panel",
        base_url="https://panel.example.com",
        username="admin",
        password="secret",
    )


def _service(username: str) -> ParsedService:
    return ParsedService(
        source_panel_id="source-panel",
        owner_id=1001,
        username_candidates=[username],
    )


async def test_existing_panel_checks_duplicates_within_that_panel(monkeypatch) -> None:
    lookup_calls: list[tuple[int, list[str]]] = []
    panel_queries: list[list[str]] = []

    async def get_by_panel(_self, panel_code: int, usernames: list[str]):
        lookup_calls.append((panel_code, usernames))
        return [SimpleNamespace(username="shared")]

    async def fetch_panel_users(_panel, usernames: list[str]):
        panel_queries.append(usernames)
        return {}

    monkeypatch.setattr(ServiceCRUD, "get_services_by_panel_and_usernames", get_by_panel)
    monkeypatch.setattr(importer, "_fetch_panel_users", fetch_panel_users)

    source_panel = _source_panel()
    db_panel = SimpleNamespace(code=4321, cookie="token")
    resolved = await importer._resolve_panel(
        source_panel,
        [_service("shared")],
        {source_panel.base_url: db_panel},
    )

    assert lookup_calls == [(4321, ["shared"])]
    assert resolved.already_in_db == {"shared"}
    assert panel_queries == [[]]


async def test_existing_panel_does_not_skip_username_from_another_panel(monkeypatch) -> None:
    global_lookup_calls = 0
    panel_queries: list[list[str]] = []

    async def get_globally(_self, _usernames: list[str]):
        nonlocal global_lookup_calls
        global_lookup_calls += 1
        return [SimpleNamespace(username="shared")]

    async def get_by_panel(_self, _panel_code: int, _usernames: list[str]):
        return []

    async def fetch_panel_users(_panel, usernames: list[str]):
        panel_queries.append(usernames)
        return {"shared": SimpleNamespace(username="shared")}

    monkeypatch.setattr(ServiceCRUD, "get_services_by_usernames", get_globally)
    monkeypatch.setattr(ServiceCRUD, "get_services_by_panel_and_usernames", get_by_panel)
    monkeypatch.setattr(importer, "_fetch_panel_users", fetch_panel_users)

    source_panel = _source_panel()
    db_panel = SimpleNamespace(code=4321, cookie="token")
    resolved = await importer._resolve_panel(
        source_panel,
        [_service("shared")],
        {source_panel.base_url: db_panel},
    )

    assert global_lookup_calls == 0
    assert resolved.already_in_db == set()
    assert panel_queries == [["shared"]]
    assert set(resolved.matched_users) == {"shared"}


async def test_new_panel_queries_all_candidates_without_global_duplicate_check(monkeypatch) -> None:
    panel_queries: list[list[str]] = []

    async def fail_existing_lookup(*_args, **_kwargs):
        raise AssertionError("A new panel must not check usernames from unrelated panels")

    async def verify_password(_base_url: str, _username: str, _password: str):
        return True, "token", []

    async def fetch_panel_users(panel, usernames: list[str]):
        assert panel.code is None
        panel_queries.append(usernames)
        return {"shared": SimpleNamespace(username="shared")}

    monkeypatch.setattr(ServiceCRUD, "get_services_by_usernames", fail_existing_lookup)
    monkeypatch.setattr(ServiceCRUD, "get_services_by_panel_and_usernames", fail_existing_lookup)
    monkeypatch.setattr(importer, "verify_panel_password", verify_password)
    monkeypatch.setattr(importer, "_fetch_panel_users", fetch_panel_users)

    resolved = await importer._resolve_panel(_source_panel(), [_service("shared")], {})

    assert resolved.status == "ok"
    assert resolved.already_in_db == set()
    assert panel_queries == [["shared"]]
    assert set(resolved.matched_users) == {"shared"}
