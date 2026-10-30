"""
Auto Card Payment Expiry Processor

This processor handles expiring auto card-to-card payment invoices that have passed the time limit.
"""

import contextlib
from datetime import datetime

from telethon import Button

from app import Kenzo
from app.db.crud.auto_card import CRUDAutoCard
from app.logger import LogType
from app.services.send_queue import enqueue

from .base import BasePaymentProcessor

AUTO_CARD_TTL_SECONDS = 1800


class AutoCardExpiryProcessor(BasePaymentProcessor):
    def __init__(self):
        super().__init__("auto_card")

    async def check_payments(self):
        now = int(datetime.now().timestamp())
        cutoff = now - AUTO_CARD_TTL_SECONDS
        crud = CRUDAutoCard()
        expired_invoices = await crud.get_expired_pending(cutoff)

        for invoice in expired_invoices:
            try:
                if invoice.msg_id:
                    with contextlib.suppress(Exception):
                        await Kenzo.delete_messages(invoice.id, invoice.msg_id)
                result = await crud.delete(code=invoice.code)

                if result:
                    user_message = (
                        "#اطلاع_رسانی\n\n"
                        f"📅 فاکتور(کارت به کارت خودکار) شماره [ {invoice.code} ] به دلیل گذشتن زمان منقضی شد.\n"
                        f"💵 مبلغ فاکتور: {invoice.first_amount:,} تومان\n"
                        f"#notification_{invoice.code}"
                    )
                    await enqueue(
                        message=user_message,
                        entity=invoice.id,
                        buttons=[[Button.inline("🚫 منقضی شد", b"no_action")]],
                    )
                    await enqueue(
                        message=(
                            "#کارت_به_کارت_خودکار\n"
                            f"👤 شناسه کاربر: <code>{invoice.id}</code> | "
                            f"<a href='tg://user?id={invoice.id}'>پروفایل کاربر</a>\n"
                            f"💡 شماره فاکتور: <code>{invoice.code}</code>\n"
                            f"💵 مبلغ فاکتور: <code>{invoice.first_amount:,}</code> تومان\n"
                            f"⏰ وضعیت: منقضی شد"
                        ),
                        log_type=LogType.AUTO_CARD,
                        parse_mode="html",
                        buttons=[[Button.inline("🚫 منقضی شد", b"no_action")]],
                    )

            except Exception:
                pass
