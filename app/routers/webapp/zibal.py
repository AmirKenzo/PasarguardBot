"""Zibal top-up from the web app: create a payment, resume the open one, check its status."""

from __future__ import annotations

from fastapi import APIRouter

from app.db.crud.zibal_payments import OPEN_STATUSES, ZibalPaymentCRUD
from app.db.models.zibal_payment import ZibalPayment
from app.logger import get_logger
from app.models.webapp import (
    BalanceZibalDepositRequest,
    BalanceZibalOpenRequest,
    BalanceZibalPaymentRequest,
    BalanceZibalPaymentResponse,
    ZibalPaymentView,
)
from app.routers.webapp.auth import authenticate_user
from app.services.payments.zibal import (
    ZibalError,
    create_deposit,
    payment_url,
    status_label,
    verify_payment,
)

logger = get_logger(__name__)
router = APIRouter()


def _view(payment: ZibalPayment) -> ZibalPaymentView:
    return ZibalPaymentView(
        id=int(payment.id),
        order_id=payment.order_id,
        amount=int(payment.amount),
        status=payment.status,
        status_label=status_label(payment.status),
        sandbox=bool(payment.sandbox),
        payment_url=payment_url(payment) if payment.status in OPEN_STATUSES else None,
        ref_id=payment.ref_id,
    )


@router.post("/webapp/balance/deposit/zibal", response_model=BalanceZibalPaymentResponse)
async def deposit_zibal(request: BalanceZibalDepositRequest) -> BalanceZibalPaymentResponse:
    try:
        user_id = await authenticate_user(init_data=request.init_data, session_token=request.session_token)
        payment = await create_deposit(user_id, request.amount, source="webapp")
        return BalanceZibalPaymentResponse(ok=True, message="لینک پرداخت ساخته شد.", payment=_view(payment))
    except (ZibalError, ValueError) as e:
        return BalanceZibalPaymentResponse(ok=False, error=getattr(e, "message", None) or str(e))
    except Exception:
        logger.exception("Zibal deposit failed")
        return BalanceZibalPaymentResponse(ok=False, error="خطا در ساخت لینک پرداخت زیبال.")


@router.post("/webapp/balance/zibal/open", response_model=BalanceZibalPaymentResponse)
async def latest_open_zibal(request: BalanceZibalOpenRequest) -> BalanceZibalPaymentResponse:
    """The caller's newest pending payment, so the page can resume after the buyer comes back."""
    try:
        user_id = await authenticate_user(init_data=request.init_data, session_token=request.session_token)
        payments = await ZibalPaymentCRUD().list_for_user(user_id)
        latest = next((p for p in payments if p.status in OPEN_STATUSES), None)
        return BalanceZibalPaymentResponse(ok=True, payment=_view(latest) if latest else None)
    except ValueError as e:
        return BalanceZibalPaymentResponse(ok=False, error=str(e))


@router.post("/webapp/balance/zibal/status", response_model=BalanceZibalPaymentResponse)
async def zibal_status(request: BalanceZibalPaymentRequest) -> BalanceZibalPaymentResponse:
    try:
        user_id = await authenticate_user(init_data=request.init_data, session_token=request.session_token)
        payment = await ZibalPaymentCRUD().get_for_user(request.payment, user_id)
        if not payment:
            return BalanceZibalPaymentResponse(ok=False, error="پرداخت پیدا نشد.")
        payment = await verify_payment(payment)
        return BalanceZibalPaymentResponse(ok=True, payment=_view(payment))
    except (ZibalError, ValueError) as e:
        return BalanceZibalPaymentResponse(ok=False, error=getattr(e, "message", None) or str(e))
