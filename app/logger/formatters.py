"""Log formatters and console handlers (colored / Rich)."""

from __future__ import annotations

import logging
import sys

from config import LOG_FORMAT


def _format_fields(record: logging.LogRecord) -> str:
    fields = getattr(record, "structured_fields", None)
    if not fields:
        return ""
    parts = []
    for key, value in fields.items():
        if value is None:
            continue
        text = str(value).replace("\n", " ")
        if " " in text:
            text = repr(text)
        parts.append(f"{key}={text}")
    return " ".join(parts)


class FileFormatter(logging.Formatter):
    """Single-line records for log files using the configured logging format."""

    def __init__(self, fmt: str | None = None) -> None:
        if fmt is None:
            fmt = LOG_FORMAT
        super().__init__(
            fmt=fmt,
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    def format(self, record: logging.LogRecord) -> str:
        fields = _format_fields(record)
        if not fields:
            return super().format(record)

        original_msg = record.msg
        original_args = record.args
        try:
            record.msg = f"{record.getMessage()} | {fields}"
            record.args = ()
            return super().format(record)
        finally:
            record.msg = original_msg
            record.args = original_args


def build_console_handler(level: int, use_rich: bool, log_format: str) -> logging.Handler:
    """Return RichHandler when enabled, else StreamHandler using ``log_format`` from config."""
    if use_rich:
        try:
            from rich.logging import RichHandler

            handler = RichHandler(
                level=level,
                rich_tracebacks=True,
                tracebacks_show_locals=False,
                markup=False,
                show_path=False,
                log_time_format="%H:%M:%S",
            )
            handler.setFormatter(logging.Formatter("%(message)s", datefmt="%H:%M:%S"))
            return handler
        except ImportError:
            pass

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)
    handler.setFormatter(FileFormatter(log_format))
    return handler
