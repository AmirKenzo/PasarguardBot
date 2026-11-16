import asyncio

from app.services.panels import api_client
from app.services.panels.api_client import PasarguardAPI, close_shared_clients
from app.telegram.shared.utils import antispam_state
from app.telegram.shared.utils.antispam_state import prune_antispam_state


def test_instances_share_one_pooled_client_per_panel() -> None:
    async def scenario() -> None:
        a = PasarguardAPI("https://panel.example.com")
        b = PasarguardAPI(base_url="https://panel.example.com/")
        other = PasarguardAPI("https://other.example.com")

        assert a.client is None  # no per-instance client kept around
        assert a._ensure_client() is b._ensure_client()
        assert a._ensure_client() is not other._ensure_client()

        await a.close()  # must not close the shared pool
        assert not b._ensure_client().is_closed

        await close_shared_clients()
        assert not api_client._shared_clients

    asyncio.run(scenario())


def test_shared_client_is_not_reused_across_event_loops() -> None:
    async def grab():
        return PasarguardAPI("https://loop.example.com")._ensure_client()

    first = asyncio.run(grab())
    second = asyncio.run(grab())
    assert first is not second
    api_client._shared_clients.clear()


def test_prune_antispam_state_drops_idle_users_and_expired_blocks(monkeypatch) -> None:
    monkeypatch.setattr(antispam_state, "user_last_message_time", {1: 0.0, 2: 1000.0})
    monkeypatch.setattr(antispam_state, "user_last_event_id", {1: 10, 2: 20})
    monkeypatch.setattr(antispam_state, "user_blocked_until", {1: 5.0, 3: 2000.0})
    monkeypatch.setattr(antispam_state, "user_spam_events", {"1_10": 0.0})

    removed = prune_antispam_state(now=1000.0)

    assert antispam_state.user_last_message_time == {2: 1000.0}
    assert antispam_state.user_last_event_id == {2: 20}
    assert antispam_state.user_blocked_until == {3: 2000.0}
    assert antispam_state.user_spam_events == {}
    assert removed == 3
