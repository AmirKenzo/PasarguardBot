"""
Iranian Gateways Payment Processor

Fallback for buyers who paid but never reached the callback page (closed the browser, lost
connection). Each run re-verifies a batch of pending payments of every gateway, least recently
checked first, and closes the ones still unpaid once they are past the local expiry.
"""

from app.db.crud.ir_gateway_payments import IrGatewayPaymentCRUD
from app.logger import get_logger
from app.services.payments.ir_gateways.service import verify_payment

from .base import BasePaymentProcessor

logger = get_logger(__name__)

POLL_BATCH = 30


class IrGatewaysProcessor(BasePaymentProcessor):
    def __init__(self):
        super().__init__("ir_gateways")

    async def check_payments(self):
        for payment in await IrGatewayPaymentCRUD().list_open(limit=POLL_BATCH):
            try:
                await verify_payment(payment)
            except Exception as e:
                logger.error("%s verify failed for %s: %s", payment.gateway, payment.order_id, e)
