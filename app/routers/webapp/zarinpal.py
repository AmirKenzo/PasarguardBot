"""Zarinpal top-up from the web app: create a payment, resume the open one, check its status."""

from __future__ import annotations

from fastapi import APIRouter

from app.db.crud.zarinpal_payments import OPEN_STATUSES, ZarinpalPaymentCRUD
from app.db.models.zarinpal_payment import ZarinpalPayment
from app.logger import get_logger
from app.models.webapp import (
    BalanceZarinpalDepositRequest,
    BalanceZarinpalOpenRequest,
    BalanceZarinpalPaymentRequest,
    BalanceZarinpalPaymentResponse,
    ZarinpalPaymentView,
)
from app.routers.webapp.auth import authenticate_user
from app.services.payments.zarinpal import (
    ZarinpalError,
    create_deposit,
    payment_url,
    status_label,
    verify_payment,
)

logger = get_logger(__name__)
router = APIRouter()


def _view(payment: ZarinpalPayment) -> ZarinpalPaymentView:
    return ZarinpalPaymentView(
        id=int(payment.id),
        order_id=payment.order_id,
        amount=int(payment.amount),
        status=payment.status,
        status_label=status_label(payment.status),
        sandbox=bool(payment.sandbox),
        payment_url=payment_url(payment) if payment.status in OPEN_STATUSES else None,
        ref_id=payment.ref_id,
    )


@router.post("/webapp/balance/deposit/zarinpal", response_model=BalanceZarinpalPaymentResponse)
async def deposit_zarinpal(request: BalanceZarinpalDepositRequest) -> BalanceZarinpalPaymentResponse:
    try:
        user_id = await authenticate_user(init_data=request.init_data, session_token=request.session_token)
        payment = await create_deposit(user_id, request.amount, source="webapp")
        return BalanceZarinpalPaymentResponse(ok=True, message="لینک پرداخت ساخته شد.", payment=_view(payment))
    except (ZarinpalError, ValueError) as e:
        return BalanceZarinpalPaymentResponse(ok=False, error=getattr(e, "message", None) or str(e))
    except Exception:
        logger.exception("Zarinpal deposit failed")
        return BalanceZarinpalPaymentResponse(ok=False, error="خطا در ساخت لینک پرداخت زرین‌پال.")


@router.post("/webapp/balance/zarinpal/open", response_model=BalanceZarinpalPaymentResponse)
async def latest_open_zarinpal(request: BalanceZarinpalOpenRequest) -> BalanceZarinpalPaymentResponse:
    """The caller's newest pending payment, so the page can resume after the buyer comes back."""
    try:
        user_id = await authenticate_user(init_data=request.init_data, session_token=request.session_token)
        payments = await ZarinpalPaymentCRUD().list_for_user(user_id)
        latest = next((p for p in payments if p.status in OPEN_STATUSES), None)
        return BalanceZarinpalPaymentResponse(ok=True, payment=_view(latest) if latest else None)
    except ValueError as e:
        return BalanceZarinpalPaymentResponse(ok=False, error=str(e))


@router.post("/webapp/balance/zarinpal/status", response_model=BalanceZarinpalPaymentResponse)
async def zarinpal_status(request: BalanceZarinpalPaymentRequest) -> BalanceZarinpalPaymentResponse:
    try:
        user_id = await authenticate_user(init_data=request.init_data, session_token=request.session_token)
        payment = await ZarinpalPaymentCRUD().get_for_user(request.payment, user_id)
        if not payment:
            return BalanceZarinpalPaymentResponse(ok=False, error="پرداخت پیدا نشد.")
        payment = await verify_payment(payment)
        return BalanceZarinpalPaymentResponse(ok=True, payment=_view(payment))
    except (ZarinpalError, ValueError) as e:
        return BalanceZarinpalPaymentResponse(ok=False, error=getattr(e, "message", None) or str(e))
