"""Support snapshots: state classification, cards, labels and panel-failure handling."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from httpx import HTTPStatusError, Request, Response

from app.services.support import (
    PANEL_ERROR_MISSING,
    PANEL_ERROR_NOT_IN_PANEL,
    PANEL_ERROR_UNREACHABLE,
    PANEL_ERROR_USERID_MISSING,
    STATE_ACTIVE,
    STATE_DISABLED,
    STATE_EXPIRED,
    STATE_EXPIRED_LIMITED,
    STATE_LIMITED,
    STATE_ON_HOLD,
    STATE_UNKNOWN,
    build_service_card,
    build_service_snapshot,
    card_state_text,
    classify_state,
    load_service_snapshot,
    load_service_states,
    service_belongs_to,
    service_warnings,
    snapshot as snapshot_module,
    state_label,
    state_style,
)

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
DAY = 86400
GB = 1024**3


def _service(**overrides) -> SimpleNamespace:
    data = {
        "code": 1234,
        "username": "ali_1",
        "id": 555,
        "in_panel": 7,
        "panel_userid": 99,
        "package_size": 30 * GB,
        "expiration_time": int(NOW.timestamp()) + 20 * DAY,
        "is_test": False,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _panel(**overrides) -> SimpleNamespace:
    data = {
        "code": 7,
        "name": "پنل اصلی",
        "base_url": "https://panel.example.com",
        "cookie": "token",
        "button_settings": {},
        "feature_settings": {},
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _panel_user(**overrides) -> SimpleNamespace:
    data = {
        "status": "active",
        "expire": NOW + timedelta(days=20),
        "data_limit": 30 * GB,
        "used_traffic": 10 * GB,
        "online_at": NOW - timedelta(hours=2),
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _settings(**overrides) -> SimpleNamespace:
    data = {"tamdid_mode": False, "upg_mode": False}
    data.update(overrides)
    return SimpleNamespace(**data)


def _http_error(status_code: int) -> HTTPStatusError:
    return HTTPStatusError(
        "panel error",
        request=Request("GET", "https://panel.example.com/api/user/99"),
        response=Response(status_code),
    )


# --------------------------------------------------------------------------- #
#  State classification                                                        #
# --------------------------------------------------------------------------- #


def test_active_service_has_green_native_style():
    state = classify_state(
        panel_status="active",
        expire_at=NOW + timedelta(days=5),
        data_limit_bytes=30 * GB,
        remaining_bytes=20 * GB,
        now=NOW,
    )

    assert state == STATE_ACTIVE
    assert state_label(state) == "🟢 فعال"
    assert state_style(state) == "success"
    assert service_warnings(build_service_snapshot(_service(), _panel(), _panel_user(online_at=None), now=NOW)) == []


def test_expired_time_is_red_even_when_panel_still_says_active():
    state = classify_state(
        panel_status="active",
        expire_at=NOW - timedelta(minutes=1),
        data_limit_bytes=30 * GB,
        remaining_bytes=20 * GB,
        now=NOW,
    )

    assert state == STATE_EXPIRED
    assert state_style(state) == "danger"


def test_volume_exhausted_is_limited():
    state = classify_state(
        panel_status="active",
        expire_at=NOW + timedelta(days=5),
        data_limit_bytes=30 * GB,
        remaining_bytes=0,
        now=NOW,
    )

    assert state == STATE_LIMITED


def test_both_problems_are_reported_together():
    state = classify_state(
        panel_status="active",
        expire_at=NOW - timedelta(days=1),
        data_limit_bytes=30 * GB,
        remaining_bytes=0,
        now=NOW,
    )

    assert state == STATE_EXPIRED_LIMITED
    assert state_label(state) == "🔴 زمان و حجم تمام شده"


def test_panel_limited_counts_as_both_when_time_is_over():
    state = classify_state(
        panel_status="limited",
        expire_at=NOW - timedelta(days=1),
        data_limit_bytes=30 * GB,
        remaining_bytes=20 * GB,
        now=NOW,
    )

    assert state == STATE_EXPIRED_LIMITED


def test_disabled_wins_over_expiry_and_volume():
    state = classify_state(
        panel_status="disabled",
        expire_at=NOW - timedelta(days=1),
        data_limit_bytes=30 * GB,
        remaining_bytes=0,
        now=NOW,
    )

    assert state == STATE_DISABLED
    assert state_label(state) == "⛔️ غیرفعال"
    assert state_style(state) is None


def test_on_hold_is_kept_apart_from_active():
    state = classify_state(
        panel_status="on_hold",
        expire_at=NOW + timedelta(days=5),
        data_limit_bytes=30 * GB,
        remaining_bytes=30 * GB,
        now=NOW,
    )

    assert state == STATE_ON_HOLD
    assert state_style(state) == "success"


def test_unlimited_plan_never_runs_out_of_volume():
    state = classify_state(
        panel_status="active",
        expire_at=NOW + timedelta(days=5),
        data_limit_bytes=0,
        remaining_bytes=None,
        now=NOW,
    )

    assert state == STATE_ACTIVE


def test_unknown_panel_status_has_no_style():
    state = classify_state(
        panel_status="weird",
        expire_at=None,
        data_limit_bytes=None,
        remaining_bytes=None,
        now=NOW,
    )

    assert state == STATE_UNKNOWN
    assert state_style(state) is None


# --------------------------------------------------------------------------- #
#  Database cards                                                              #
# --------------------------------------------------------------------------- #


def test_card_marks_expired_service_from_stored_expiry():
    service = _service(expiration_time=int(NOW.timestamp()) - DAY)

    card = build_service_card(service, _panel(), now=NOW)

    assert card.state == STATE_EXPIRED
    assert card_state_text(card) == "🔴 منقضی"
    assert state_style(card.state) == "danger"


def test_card_warns_when_expiry_is_close_without_inventing_a_colour():
    service = _service(expiration_time=int(NOW.timestamp()) + 2 * DAY)

    card = build_service_card(service, _panel(), now=NOW)

    assert card.state == STATE_ACTIVE
    assert card.expiring_soon is True
    assert card_state_text(card).startswith("🟡")
    assert state_style(card.state) == "success"


def test_card_without_stored_expiry_is_unknown():
    card = build_service_card(_service(expiration_time=None), None, now=NOW)

    assert card.state == STATE_UNKNOWN
    assert card.panel_name == "پنل نامشخص"
    assert card_state_text(card) == "⚪️ نامشخص"


def test_ownership_is_strict():
    service = _service(id=555)

    assert service_belongs_to(service, 555) is True
    assert service_belongs_to(service, 556) is False
    assert service_belongs_to(None, 555) is False


# --------------------------------------------------------------------------- #
#  Live snapshots                                                              #
# --------------------------------------------------------------------------- #


def test_snapshot_carries_remaining_volume_and_last_connection():
    snapshot = build_service_snapshot(_service(), _panel(), _panel_user(), now=NOW)

    assert snapshot.panel_available is True
    assert snapshot.state == STATE_ACTIVE
    assert snapshot.remaining_bytes == 20 * GB
    assert snapshot.used_bytes == 10 * GB
    assert snapshot.online_at == NOW - timedelta(hours=2)
    assert snapshot.expiring_soon is False
    assert snapshot.low_volume is False


def test_snapshot_flags_low_volume_with_a_yellow_warning():
    snapshot = build_service_snapshot(
        _service(),
        _panel(),
        _panel_user(used_traffic=28 * GB),
        now=NOW,
    )

    assert snapshot.low_volume is True
    assert all(warning.startswith("🟡") for warning in service_warnings(snapshot))


def test_snapshot_of_unlimited_plan_has_no_remaining_count():
    snapshot = build_service_snapshot(_service(), _panel(), _panel_user(data_limit=0), now=NOW)

    assert snapshot.unlimited is True
    assert snapshot.remaining_bytes is None
    assert snapshot.low_volume is False


def test_snapshot_without_panel_user_keeps_the_stored_expiry():
    snapshot = build_service_snapshot(
        _service(),
        _panel(),
        None,
        now=NOW,
        panel_error=PANEL_ERROR_UNREACHABLE,
    )

    assert snapshot.panel_available is False
    assert snapshot.state == STATE_UNKNOWN
    assert snapshot.panel_error == PANEL_ERROR_UNREACHABLE
    assert snapshot.expire_at == datetime.fromtimestamp(int(NOW.timestamp()) + 20 * DAY, tz=UTC)


async def test_panel_exception_never_breaks_the_snapshot(monkeypatch):
    class _DownAPI:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def get_user_by_id(self, **kwargs):
            raise RuntimeError("panel down")

    monkeypatch.setattr(snapshot_module, "PasarguardAPI", _DownAPI)

    snapshot = await load_service_snapshot(_service(), panel=_panel(), settings=_settings(), now=NOW)

    assert snapshot.panel_available is False
    assert snapshot.panel_error == PANEL_ERROR_UNREACHABLE
    assert snapshot.state == STATE_UNKNOWN
    assert snapshot.can_renew is False
    assert snapshot.can_buy_volume is False


async def test_panel_404_is_reported_as_not_in_panel(monkeypatch):
    class _MissingAPI:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def get_user_by_id(self, **kwargs):
            raise _http_error(404)

    monkeypatch.setattr(snapshot_module, "PasarguardAPI", _MissingAPI)

    snapshot = await load_service_snapshot(_service(), panel=_panel(), settings=_settings(), now=NOW)

    assert snapshot.panel_error == PANEL_ERROR_NOT_IN_PANEL


async def test_missing_panel_is_reported(monkeypatch):
    async def _no_panel(code):
        return None

    async def _settings_row():
        return _settings()

    monkeypatch.setattr(snapshot_module.PanelsManager, "get_panel_by_code", lambda self, code: _no_panel(code))
    monkeypatch.setattr(snapshot_module.SettingsManager, "get_settings", lambda self: _settings_row())

    snapshot = await load_service_snapshot(_service(in_panel=404), settings=None, now=NOW)

    assert snapshot.panel_available is False
    assert snapshot.panel_error == PANEL_ERROR_MISSING


async def test_missing_panel_user_id_is_reported():
    snapshot = await load_service_snapshot(
        _service(panel_userid=None),
        panel=_panel(),
        settings=_settings(),
        now=NOW,
    )

    assert snapshot.panel_available is False
    assert snapshot.panel_error == PANEL_ERROR_USERID_MISSING


async def test_renew_and_volume_buttons_follow_bot_and_panel_settings(monkeypatch):
    panel = _panel(
        feature_settings={"service_upgrade": {"volume_plans": [{"id": 1, "storage_gb": 10, "price": 5000}]}},
    )
    settings = _settings(tamdid_mode=True, upg_mode=True)

    class _Api:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def get_user_by_id(self, **kwargs):
            return _panel_user()

    async def _not_fair(service):
        return False

    monkeypatch.setattr(snapshot_module, "PasarguardAPI", _Api)
    monkeypatch.setattr(snapshot_module, "service_uses_fair_usage_plan", _not_fair)

    snapshot = await load_service_snapshot(_service(), panel=panel, settings=settings, now=NOW)

    assert snapshot.can_renew is True
    assert snapshot.can_buy_volume is True


async def test_fair_usage_plan_has_no_volume_button(monkeypatch):
    panel = _panel(
        feature_settings={"service_upgrade": {"volume_plans": [{"id": 1, "storage_gb": 10, "price": 5000}]}},
    )
    settings = _settings(tamdid_mode=True, upg_mode=True)

    class _Api:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def get_user_by_id(self, **kwargs):
            return _panel_user()

    async def _fair(service):
        return True

    monkeypatch.setattr(snapshot_module, "PasarguardAPI", _Api)
    monkeypatch.setattr(snapshot_module, "service_uses_fair_usage_plan", _fair)

    snapshot = await load_service_snapshot(_service(), panel=panel, settings=settings, now=NOW)

    assert snapshot.can_renew is True
    assert snapshot.can_buy_volume is False


async def test_test_service_cannot_be_renewed(monkeypatch):
    class _Api:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def get_user_by_id(self, **kwargs):
            return _panel_user()

    monkeypatch.setattr(snapshot_module, "PasarguardAPI", _Api)

    snapshot = await load_service_snapshot(
        _service(is_test=True),
        panel=_panel(),
        settings=_settings(tamdid_mode=True, upg_mode=True),
        now=NOW,
    )

    assert snapshot.can_renew is False
    assert snapshot.can_buy_volume is False


# --------------------------------------------------------------------------- #
#  Picker states                                                               #
# --------------------------------------------------------------------------- #


async def test_picker_row_uses_the_live_panel_state(monkeypatch):
    class _Api:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def get_user_by_id(self, **kwargs):
            return _panel_user(status="limited", used_traffic=30 * GB)

    monkeypatch.setattr(snapshot_module, "PasarguardAPI", _Api)

    states = await load_service_states([_service()], panels_by_code={7: _panel()}, now=NOW)

    assert states[0].panel_available is True
    assert states[0].state == STATE_LIMITED
    assert card_state_text(states[0]) == "🔴 حجم تمام"
    assert state_style(states[0].state) == "danger"


async def test_picker_row_falls_back_to_the_stored_state(monkeypatch):
    class _Api:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def get_user_by_id(self, **kwargs):
            raise RuntimeError("panel down")

    monkeypatch.setattr(snapshot_module, "PasarguardAPI", _Api)

    states = await load_service_states([_service()], panels_by_code={7: _panel()}, now=NOW)

    assert states[0].panel_available is False
    assert states[0].state == STATE_ACTIVE  # from the stored expiry
    assert state_style(states[0].state) == "success"


async def test_picker_row_without_panel_user_id_is_not_fetched(monkeypatch):
    calls = []

    class _Api:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def get_user_by_id(self, **kwargs):
            calls.append(kwargs)
            return _panel_user()

    monkeypatch.setattr(snapshot_module, "PasarguardAPI", _Api)

    states = await load_service_states(
        [_service(panel_userid=None), _service(code=2222)],
        panels_by_code={7: _panel()},
        now=NOW,
    )

    assert len(calls) == 1
    assert states[0].panel_available is False
    assert states[1].panel_available is True
