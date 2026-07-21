"""
Manual Card Payment Processor — rule-based auto confirm (auto_approve_at on transaction).
"""

from datetime import datetime

from telethon import Button

from app import Kenzo
from app.db.crud.manual_auto_approve_rules import build_manual_card_log_caption
from app.db.crud.settings import SettingsManager
from app.db.crud.transactions import TransactionCRUD
from app.db.crud.user import UserCRUD
from app.services.billing.direct_pay_fulfillment import try_fulfill_after_manual_credit

from .base import BasePaymentProcessor


class ManualCardProcessor(BasePaymentProcessor):
    def __init__(self):
        super().__init__("manual")

    async def check_payments(self):
        settings = await SettingsManager().get_settings()
        if not settings or not settings.manual_auto_confirm:
            return

        crud = TransactionCRUD()
        now = int(datetime.now().timestamp())
        for tx in await crud.get_pending_manual_due_auto_approve(now):
            if tx.status != "pending":
                continue
            result = await crud.approve_manual(tx)
            if not result:
                continue
            new_amount = result["new_balance"]
            bonus = result["bonus"]
            try:
                fulfilled = await try_fulfill_after_manual_credit(int(tx.id))
                if not fulfilled:
                    mesg = (
                        "**✅ تراکنش کارت به کارت (دستی) شما تایید شد**\n\n"
                        f"👤 **شناسه شما:** `{tx.user_id}`\n"
                        f"💰 مبلغ `{int(tx.amount):,}` تومان به حساب شما اضافه شد.\n"
                    )
                    if bonus > 0:
                        mesg += f"🎁 بونوس: +{bonus:,} تومان ({settings.manual_bonus_percent}%)\n"
                        mesg += f"💰 مجموع: {result['total']:,} تومان\n"
                    mesg += "👜 موجودی شما به کیف پولتون در بات اضافه شده\n💡 اکنون می‌توانید از ربات خرید کنید."
                    await Kenzo.send_message(
                        tx.user_id,
                        mesg,
                        buttons=[[Button.inline(text=f"موجودی جدید {new_amount:,} تومان", data="no_action")]],
                    )
                if tx.message_id and tx.message_chat_id:
                    reduser = await UserCRUD().read_user(tx.user_id)
                    log_text = await build_manual_card_log_caption(
                        user_id=tx.user_id,
                        amount=int(tx.amount),
                        header="✅ تراکنش خودکار تایید شد.",
                        reduser=reduser,
                        new_balance=new_amount,
                        bonus=bonus,
                        total=result["total"],
                        bonus_percent=settings.manual_bonus_percent,
                        created_at=tx.created_at,
                        completed_at=result["completed_at"],
                    )
                    await Kenzo.edit_message(
                        tx.message_chat_id,
                        tx.message_id,
                        log_text,
                        buttons=[[Button.inline(text="🌟 تراکنش به صورت خودکار تایید شد", data="no_action")]],
                    )
            except Exception:
                pass
