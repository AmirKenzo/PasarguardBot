"""Central logging configuration constants (env values live in config.py)."""

from __future__ import annotations

import logging

from config import LOG_LEVEL

APP_LOG_FILENAME = "app.log"
ERROR_LOG_FILENAME = "error.log"

# Console message column width for alignment
MESSAGE_PAD = 36

# Third-party loggers — keep terminal quiet
QUIET_LOGGERS: dict[str, int] = {
    "httpx": logging.WARNING,
    "httpcore": logging.WARNING,
    "hpack": logging.WARNING,
    "telethon": logging.WARNING,
    "telethon.network": logging.ERROR,
    "telethon.client": logging.WARNING,
    "apscheduler": logging.WARNING,
    "apscheduler.scheduler": logging.WARNING,
    "tzlocal": logging.WARNING,
    "uvicorn": logging.INFO,
    "uvicorn.access": logging.WARNING,
    "uvicorn.error": logging.INFO,
    "fastapi": logging.WARNING,
    "sqlalchemy.engine": logging.WARNING,
    "asyncio": logging.WARNING,
}

# Application log namespace
APP_LOGGER_NAME = "PasarGuardBot"


def resolve_log_level(name: str | None = None) -> int:
    """Map string level name to logging constant; default from config.LOG_LEVEL."""
    if name is None:
        name = LOG_LEVEL
    level_name = str(name).upper()
    return getattr(logging, level_name, logging.INFO)
