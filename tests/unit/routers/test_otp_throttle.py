"""Phone OTP login must not allow unlimited codes or unlimited guesses."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.routers.webapp import auth as auth_module, state

PHONE = "09120000000"
USER_ID = 77


@pytest.fixture(autouse=True)
def clean_state() -> None:
    state.otp_sessions.clear()
    state.otp_start_history.clear()
    state.otp_failure_history.clear()


@pytest.fixture
def bot(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Known user with this phone; captures codes the bot would send."""
    sent: list[str] = []
    user = SimpleNamespace(id=USER_ID, number=PHONE)

    async def get_user_by_phone(self, phone: str):
        return user if phone == PHONE else None

    async def send_code(user_id: int, code: str) -> None:
        sent.append(code)

    monkeypatch.setattr(auth_module.UserCRUD, "get_user_by_phone", get_user_by_phone)
    monkeypatch.setattr(auth_module, "_send_telegram_code", send_code)
    return sent


def _request(ip: str = "203.0.113.5") -> SimpleNamespace:
    return SimpleNamespace(headers={}, client=SimpleNamespace(host=ip))


def _start(phone: str = PHONE, ip: str = "203.0.113.5"):
    return asyncio.run(auth_module.start_phone_login(SimpleNamespace(phone=phone), _request(ip)))


def _verify(code: str):
    return asyncio.run(auth_module.verify_phone_login(SimpleNamespace(phone=PHONE, code=code)))


def _wrong(code: str) -> str:
    return f"{(int(code) + 1) % 1_000_000:06d}"


def test_code_requests_per_phone_are_limited(bot: list[str]) -> None:
    results = [_start(ip=f"198.51.100.{i}") for i in range(state.OTP_MAX_STARTS_PER_PHONE + 1)]
    assert [r.ok for r in results] == [True] * state.OTP_MAX_STARTS_PER_PHONE + [False]
    assert len(bot) == state.OTP_MAX_STARTS_PER_PHONE


def test_code_requests_per_ip_are_limited_even_for_unknown_numbers(bot: list[str]) -> None:
    results = [_start(phone=f"0935{i:07d}") for i in range(state.OTP_MAX_STARTS_PER_IP + 1)]
    assert results[-1].error == auth_module._OTP_THROTTLED_ERROR


def test_new_code_does_not_reset_wrong_guess_counter(bot: list[str], monkeypatch: pytest.MonkeyPatch) -> None:
    # Lift the per-phone start limit so only the cumulative failure cap is under test.
    monkeypatch.setattr(state, "OTP_MAX_STARTS_PER_PHONE", 100)
    guesses = 0
    while guesses < state.OTP_MAX_FAILURES_PER_PHONE:
        assert _start().ok is True
        for _ in range(3):
            _verify(_wrong(bot[-1]))
            guesses += 1

    assert _start().ok is False
    assert _verify(bot[-1]).ok is False


def test_correct_code_logs_in_and_clears_failures(bot: list[str], monkeypatch: pytest.MonkeyPatch) -> None:
    async def get_session_version(self, user_id: int) -> int:
        return 0

    async def build_payload(user_id: int, user_record=None) -> dict:
        return {"ok": True}

    async def notify(*args, **kwargs) -> None:
        return None

    monkeypatch.setattr(auth_module.UserCRUD, "get_session_version", get_session_version)
    monkeypatch.setattr(auth_module, "create_session_token", lambda uid, session_version: "token")
    monkeypatch.setattr(auth_module, "build_user_payload_no_services", build_payload)
    monkeypatch.setattr(auth_module, "_send_login_notification", notify)

    assert _start().ok is True
    _verify(_wrong(bot[-1]))
    result = _verify(bot[-1])

    assert result.ok is True
    assert result.session_token == "token"
    assert state.otp_failure_history.get(state.otp_key(PHONE)) is None


def test_codes_are_six_digits(bot: list[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(state, "OTP_MAX_STARTS_PER_PHONE", 50)
    monkeypatch.setattr(state, "OTP_MAX_STARTS_PER_IP", 50)
    for _ in range(20):
        _start()
    assert all(len(code) == 6 and code.isdigit() for code in bot)
