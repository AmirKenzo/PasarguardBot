"""Top-up through any Iranian direct gateway from the web app: create, resume the open one, check status."""

from __future__ import annotations

from fastapi import APIRouter

from app.db.crud.ir_gateway_payments import OPEN_STATUSES, IrGatewayPaymentCRUD
from app.db.models.ir_gateway_payment import IrGatewayPayment
from app.logger import get_logger
from app.models.webapp import (
    BalanceIrGatewayDepositRequest,
    BalanceIrGatewayOpenRequest,
    BalanceIrGatewayPaymentRequest,
    BalanceIrGatewayPaymentResponse,
    IrGatewayPaymentView,
)
from app.routers.webapp.auth import authenticate_user
from app.services.payments.ir_gateways.providers import GatewayError
from app.services.payments.ir_gateways.service import (
    create_deposit,
    gateway_title,
    payment_url,
    status_label,
    verify_payment,
)

logger = get_logger(__name__)
router = APIRouter()


def _view(payment: IrGatewayPayment) -> IrGatewayPaymentView:
    return IrGatewayPaymentView(
        id=int(payment.id),
        gateway=payment.gateway,
        gateway_title=gateway_title(payment.gateway),
        order_id=payment.order_id,
        amount=int(payment.amount),
        status=payment.status,
        status_label=status_label(payment.status),
        sandbox=bool(payment.sandbox),
        payment_url=payment_url(payment) if payment.status in OPEN_STATUSES else None,
        ref_id=payment.ref_id,
    )


@router.post("/webapp/balance/ir-gateway/deposit", response_model=BalanceIrGatewayPaymentResponse)
async def ir_gateway_deposit(request: BalanceIrGatewayDepositRequest) -> BalanceIrGatewayPaymentResponse:
    try:
        user_id = await authenticate_user(init_data=request.init_data, session_token=request.session_token)
        payment = await create_deposit(request.gateway, user_id, request.amount, source="webapp")
        return BalanceIrGatewayPaymentResponse(ok=True, message="لینک پرداخت ساخته شد.", payment=_view(payment))
    except (GatewayError, ValueError) as e:
        return BalanceIrGatewayPaymentResponse(ok=False, error=getattr(e, "message", None) or str(e))
    except Exception:
        logger.exception("Gateway deposit failed for %s", request.gateway)
        return BalanceIrGatewayPaymentResponse(ok=False, error="خطا در ساخت لینک پرداخت.")


@router.post("/webapp/balance/ir-gateway/open", response_model=BalanceIrGatewayPaymentResponse)
async def ir_gateway_open(request: BalanceIrGatewayOpenRequest) -> BalanceIrGatewayPaymentResponse:
    """The caller's newest pending payment for this gateway, so the page can resume after the buyer comes back."""
    try:
        user_id = await authenticate_user(init_data=request.init_data, session_token=request.session_token)
        payments = await IrGatewayPaymentCRUD().list_for_user(user_id, gateway=request.gateway)
        latest = next((p for p in payments if p.status in OPEN_STATUSES), None)
        return BalanceIrGatewayPaymentResponse(ok=True, payment=_view(latest) if latest else None)
    except ValueError as e:
        return BalanceIrGatewayPaymentResponse(ok=False, error=str(e))


@router.post("/webapp/balance/ir-gateway/status", response_model=BalanceIrGatewayPaymentResponse)
async def ir_gateway_status(request: BalanceIrGatewayPaymentRequest) -> BalanceIrGatewayPaymentResponse:
    try:
        user_id = await authenticate_user(init_data=request.init_data, session_token=request.session_token)
        payment = await IrGatewayPaymentCRUD().get_for_user(request.payment, user_id)
        if not payment:
            return BalanceIrGatewayPaymentResponse(ok=False, error="پرداخت پیدا نشد.")
        payment = await verify_payment(payment)
        return BalanceIrGatewayPaymentResponse(ok=True, payment=_view(payment))
    except (GatewayError, ValueError) as e:
        return BalanceIrGatewayPaymentResponse(ok=False, error=getattr(e, "message", None) or str(e))
