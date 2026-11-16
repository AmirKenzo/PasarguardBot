"""Periodic memory housekeeping: prune per-user in-memory caches and give freed heap back to the OS."""

from __future__ import annotations

import ctypes
import ctypes.util
import gc
import sys

from app.db.crud.user import prune_user_local_caches
from app.logger import LogTag, get_logger
from app.telegram.shared.utils.antispam_state import prune_antispam_state
from app.telegram.shared.utils.maintenance import prune_offline_notifications
from app.telegram.shared.utils.rate_limit import prune_callback_debounce
from app.telegram.state.store import prune_step_local_cache

logger = get_logger(__name__)


def _load_malloc_trim():
    """Return glibc ``malloc_trim`` if available (Linux/glibc only), else None."""
    if not sys.platform.startswith("linux"):
        return None
    try:
        libc = ctypes.CDLL(ctypes.util.find_library("c") or "libc.so.6")
        trim = libc.malloc_trim
    except OSError, AttributeError:
        return None
    trim.argtypes = [ctypes.c_size_t]
    trim.restype = ctypes.c_int
    return trim


_malloc_trim = _load_malloc_trim()


def release_memory() -> None:
    """Run a full GC and ask glibc to return free arena pages to the OS.

    CPython frees objects into glibc arenas but glibc rarely hands those pages
    back, so RSS stays at its peak after bursty work (jobs, broadcasts, large
    panel responses). ``malloc_trim(0)`` releases them.
    """
    gc.collect()
    if _malloc_trim is not None:
        try:
            _malloc_trim(0)
        except Exception as exc:
            logger.debug("%s malloc_trim failed: %s", LogTag.JOB, exc)


async def memory_housekeeping() -> None:
    removed = (
        prune_antispam_state()
        + prune_callback_debounce()
        + prune_offline_notifications()
        + prune_step_local_cache()
        + prune_user_local_caches()
    )
    release_memory()
    logger.debug("%s memory_housekeeping | pruned=%s", LogTag.JOB, removed)
