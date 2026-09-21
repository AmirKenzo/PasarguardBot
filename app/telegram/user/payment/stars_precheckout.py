STARS_INVOICE_TTL_SECONDS = 1800  # keep in sync with app/jobs/payments/stars.py


def stars_precheckout_ok(tx, *, now: int) -> bool:
    """True only when Telegram should be told success=True."""
    if tx is None:
        return False
    if getattr(tx, "status", None) != "pending":
        return False
    created = int(getattr(tx, "created_at", 0) or 0)
    return created + STARS_INVOICE_TTL_SECONDS > now
