from app.jobs.payments.stars import STARS_INVOICE_TTL_SECONDS


def stars_precheckout_ok(tx, *, now: int) -> bool:
    """True only when Telegram should be told success=True."""
    if tx is None:
        return False
    if getattr(tx, "status", None) != "pending":
        return False
    created = int(getattr(tx, "created_at", 0) or 0)
    return created + STARS_INVOICE_TTL_SECONDS > now
