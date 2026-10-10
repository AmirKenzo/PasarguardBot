"""
Zarinpal Payment Processor

Fallback for buyers who paid but never reached the callback page (closed the browser, lost
connection). Each run re-verifies a batch of pending payments, least recently checked first,
and closes the ones Zarinpal still reports unpaid once they are past the local expiry.
"""

from app.db.crud.zarinpal_payments import ZarinpalPaymentCRUD
from app.logger import get_logger
from app.services.payments.zarinpal import verify_payment

from .base import BasePaymentProcessor

logger = get_logger(__name__)

POLL_BATCH = 20


class ZarinpalProcessor(BasePaymentProcessor):
    def __init__(self):
        super().__init__("zarinpal")

    async def check_payments(self):
        for payment in await ZarinpalPaymentCRUD().list_open(limit=POLL_BATCH):
            try:
                await verify_payment(payment)
            except Exception as e:
                logger.error("Zarinpal verify failed for %s: %s", payment.order_id, e)
