"""Charge the wallet before delivering a paid change, refunding if delivery fails."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.db.crud.user import debit_Money_if_sufficient, update_Money
from app.logger import get_logger

logger = get_logger(__name__)


async def charge_then_apply[T](user_id: int, price: int, apply: Callable[[], Awaitable[T]]) -> tuple[T, int] | None:
    """Atomically debit ``price``, then run ``apply``.

    Returns ``None`` (nothing applied, nothing charged) when the balance cannot cover
    ``price``. Otherwise returns ``(apply_result, new_balance)``. If ``apply`` raises,
    the charge is refunded and the exception is re-raised.

    Debiting first (with a row lock and no negative balance) is what stops concurrent
    requests from all passing a balance check and stacking paid upgrades.
    """
    price = int(price)
    new_balance = await debit_Money_if_sufficient(user_id=user_id, amount=price)
    if new_balance is None:
        return None
    try:
        result = await apply()
    except Exception:
        refund_balance = await update_Money(user_id=user_id, Money=price)
        logger.warning("Paid change failed, refunded user=%s price=%s balance=%s", user_id, price, refund_balance)
        raise
    return result, int(new_balance)
