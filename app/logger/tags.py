"""Log area tags — use as prefix in log messages: ``logger.info("%s ...", LogTag.BOOT)``."""

from __future__ import annotations

from enum import Enum, StrEnum


class LogTag(StrEnum):
    BOOT = "BOOT"
    API = "API"
    TELEGRAM = "TELEGRAM"
    PLUGIN = "PLUGIN"
    SCHEDULER = "SCHEDULER"
    JOB = "JOB"
    MIDDLEWARE = "MIDDLEWARE"
    VERSION = "VERSION"
    REDIS = "REDIS"

    def __str__(self) -> str:
        return f"[{self.value}]"


class LogType(Enum):
    """Enum for different types of log messages."""

    # Payment related logs
    MANUAL_CARD = "manual_card"
    AUTO_CARD = "auto_card"
    CRYPTO = "crypto"
    STARS = "stars"

    # System related logs
    OTHER = "other"
    BACKUP = "backup"
    PANEL_UPDATE = "panel_update"
    SERVICE_EXPIRY = "service_expiry"
    LOW_VOLUME = "low_volume"
    USER_REGISTRATION = "user_registration"
    SYSTEM_ERROR = "system_error"

    # Public sales card, separate from the detailed admin purchase log
    PURCHASE = "purchase"

    # Transaction related logs
    TRANSACTION_APPROVED = "transaction_approved"
    TRANSACTION_REJECTED = "transaction_rejected"
    TRANSACTION_EXPIRED = "transaction_expired"

    # Reseller related logs
    RESELLER = "reseller"

    # Service related logs
    SERVICE_CREATED = "service_created"
    SERVICE_DELETED = "service_deleted"
    SERVICE_RENEWED = "service_renewed"
    ACCOUNT_REPLACEMENT = "account_replacement"

    def __str__(self):
        return self.value
