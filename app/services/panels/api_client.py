"""Pooled PasarguardAPI client.

The upstream ``pasarguard.PasarguardAPI`` builds a brand-new ``httpx.AsyncClient``
for every instance, and the bot creates a throwaway instance per API call without
ever closing it. Each of those clients keeps its own connection pool, TLS context
and (for open keep-alive sockets) a 256 KiB SSL read buffer alive until the panel
drops the connection, so RSS keeps climbing under normal traffic.

This drop-in subclass routes every request through one shared, bounded
``httpx.AsyncClient`` per (event loop, base_url, transport options), so all call
sites reuse the same few connections. Import ``PasarguardAPI`` from here instead
of from ``pasarguard``.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any

import httpx
from pasarguard import PasarguardAPI as _UpstreamPasarguardAPI

from app.logger import get_logger

logger = get_logger(__name__)

_POOL_LIMITS = httpx.Limits(max_connections=20, max_keepalive_connections=5, keepalive_expiry=15.0)

_ClientKey = tuple[str, Any, bool, Any, bool]
# key -> (owning event loop, shared client)
_shared_clients: dict[_ClientKey, tuple[asyncio.AbstractEventLoop, httpx.AsyncClient]] = {}


def _current_loop() -> asyncio.AbstractEventLoop | None:
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return None


def _get_shared_client(base_url: str, timeout: Any, verify: bool, proxy: Any, trust_env: bool) -> httpx.AsyncClient:
    loop = _current_loop()
    key: _ClientKey = (base_url, timeout, verify, proxy, trust_env)
    entry = _shared_clients.get(key)
    if entry is not None:
        owner_loop, client = entry
        if owner_loop is loop and not client.is_closed:
            return client
        # Client belongs to a dead/other loop (e.g. tests): drop it, its loop owns the sockets.
        _shared_clients.pop(key, None)

    client = httpx.AsyncClient(
        base_url=base_url,
        verify=verify,
        timeout=timeout,
        proxy=proxy,
        trust_env=trust_env,
        limits=_POOL_LIMITS,
    )
    if loop is not None:
        _shared_clients[key] = (loop, client)
    return client


async def close_shared_clients() -> None:
    """Close every pooled client owned by the running loop (call on shutdown)."""
    loop = _current_loop()
    for key, (owner_loop, client) in list(_shared_clients.items()):
        if owner_loop is not loop:
            continue
        _shared_clients.pop(key, None)
        with contextlib.suppress(Exception):
            await client.aclose()


class PasarguardAPI(_UpstreamPasarguardAPI):
    """``pasarguard.PasarguardAPI`` that shares pooled HTTP connections per panel."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if not self.ssh_host and self.client is not None:
            # Upstream eagerly builds a per-instance client; it has no open sockets yet,
            # so dropping the reference is enough — requests use the shared pool instead.
            self.client = None

    def _ensure_client(self) -> httpx.AsyncClient:
        if self.ssh_host:
            return super()._ensure_client()
        return _get_shared_client(self.base_url, self.timeout, self.verify, self.proxy, self.trust_env)

    async def close(self) -> None:
        # The pooled client is shared by every instance; only close per-instance SSH resources.
        if self.ssh_host:
            await super().close()
