"""Shared error handling for WebApp endpoints.

Unexpected exceptions must never reach the user verbatim: their text can carry
panel URLs, SQL or stack details. Endpoints return :data:`INTERNAL_ERROR`
instead, and the frontend translates it (``apiErrors.internalError``).
"""

from app.logger import get_logger

logger = get_logger(__name__)

# Error code the frontend maps to a translated "something went wrong, try again" message.
INTERNAL_ERROR = "internal_error"

SESSION_INVALID = "session_invalid"


def internal_error(context: str) -> str:
    """Log the exception being handled with its traceback and return the generic error code.

    Call it only from inside an ``except`` block so the traceback is captured.
    """
    logger.exception("webapp %s failed", context)
    return INTERNAL_ERROR
