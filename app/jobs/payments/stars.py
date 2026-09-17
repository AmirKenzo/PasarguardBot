"""
Stars Payment Expiry Processor

This processor handles expiring Stars payment invoices that have passed the time limit.
"""

import contextlib
from datetime import datetime

from sqlalchemy.future import select
from telethon import Button

from app import Kenzo
from app.db.base import AsyncSessionLocal as Session
from app.db.models.stars_transaction import StarsTransaction
from app.logger import LogType
from app.services.send_queue import enqueue

from .base import BasePaymentProcessor

_STARS_INVOICE_TTL_SECONDS = 1800


class StarsExpiryProcessor(BasePaymentProcessor):
    def __init__(self):
        super().__init__("stars")

    async def check_payments(self):
        now = int(datetime.now().timestamp())
        expire_before = now - _STARS_INVOICE_TTL_SECONDS
        async with Session() as session:
            result = await session.execute(
                select(StarsTransaction).where(
                    StarsTransaction.status == "pending",
                    StarsTransaction.created_at <= expire_before,
                )
            )
            pending = list(result.scalars().all())
            if not pending:
                return

            for tx in pending:
                tx.status = "expired"
            await session.commit()

        for tx in pending:
            try:
                if hasattr(tx, "message_id") and tx.message_id:
                    with contextlib.suppress(Exception):
                        await Kenzo.delete_messages(tx.user_id, tx.message_id)

                await Kenzo.send_message(
                    tx.user_id,
                    f"#Stars\n⌛️ فاکتور شماره `{tx.invoice_no}` منقضی شد.",
                    buttons=[[Button.inline("🚫 منقضی شد", b"no_action")]],
                )
                await enqueue(
                    message=f"#Stars\nفاکتور `{tx.invoice_no}` کاربر `{tx.user_id}` منقضی شد.",
                    log_type=LogType.STARS,
                    buttons=[[Button.inline("🚫 منقضی شد", b"no_action")]],
                )

            except Exception:
                pass
