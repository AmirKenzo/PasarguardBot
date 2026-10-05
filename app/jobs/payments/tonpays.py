"""
TonPays Payment Processor

Fallback poller for TonPays invoices in case a webhook is missed. TonPays allows 60
create/check calls per minute, so each run checks at most POLL_BATCH open invoices,
least recently checked first.
"""

from app.db.crud.tonpays_invoices import TonPaysInvoiceCRUD
from app.logger import get_logger
from app.services.payments.tonpays import refresh_invoice

from .base import BasePaymentProcessor

logger = get_logger(__name__)

POLL_BATCH = 30


class TonPaysProcessor(BasePaymentProcessor):
    def __init__(self):
        super().__init__("tonpays")

    async def check_payments(self):
        for invoice in await TonPaysInvoiceCRUD().list_open(limit=POLL_BATCH):
            try:
                await refresh_invoice(invoice)
            except Exception as e:
                logger.error("TonPays refresh failed for %s: %s", invoice.order_id, e)
