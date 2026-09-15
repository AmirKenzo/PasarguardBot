"""Write operations used by the panel routes. Each one records an audit row."""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy import delete, select, update

from app.db.base import AsyncSessionLocal as Session
from app.db.crud.cards import ManualCardManager
from app.db.crud.manual_auto_approve_rules import ManualAutoApproveRuleCRUD
from app.db.crud.receipt_hash import ReceiptHashCRUD
from app.db.crud.settings import SettingsManager
from app.db.crud.transactions import TransactionCRUD
from app.db.models.discount_codes import DiscountCode
from app.db.models.panels import Panels
from app.db.models.plans import Plan
from app.db.models.reseller_accounts import ResellerAccount
from app.db.models.reseller_plans import ResellerPlan
from app.db.models.services import Service
from app.db.models.transaction import Transaction
from app.db.models.user import User
from app.logger import get_logger
from app.panel import audit
from app.routers.panel.auth import PanelActor
from app.services.panels.settings import resolve_panel_update_kwargs
from app.telegram.admin.settings_payment.texts import (
    CARD_HOLDER_NOT_SET,
    TX_APPROVED_USER_MESSAGE,
    TX_CARD_MISMATCH_USER_MESSAGE,
    TX_RECEIPT_FIX_USER_MESSAGE,
    TX_REJECTED_USER_MESSAGE,
)
from app.utils.text.bot_texts import get_bot_text

log = get_logger(__name__)


async def _audit(ctx: PanelActor, action: str, **kwargs: Any) -> None:
    await audit.record(
        actor_id=ctx.user_id,
        actor_username=ctx.username,
        action=action,
        ip=ctx.ip,
        **kwargs,
    )


async def notify_user(user_id: int, text: str) -> None:
    """Send a Telegram message to the user; failures are logged and ignored."""
    try:
        from app import Kenzo

        if Kenzo.is_connected():
            await Kenzo.send_message(int(user_id), text)
    except Exception as exc:
        log.info("panel: could not notify user %s: %s", user_id, exc)


# --------------------------------------------------------------------------- #
#  Users                                                                        #
# --------------------------------------------------------------------------- #


async def adjust_balance(ctx: PanelActor, user_id: int, delta: int, *, notify: bool = True) -> int | None:
    """Add (positive) or subtract (negative) wallet credit. Returns the new balance."""
    async with Session() as session:
        user = (await session.execute(select(User).where(User.id == user_id))).scalars().first()
        if user is None:
            return None
        current = int(user.amount or 0)
        new_balance = max(0, current + int(delta))
        user.amount = new_balance
        await session.commit()

    await _audit(
        ctx,
        "balance_add" if delta >= 0 else "balance_subtract",
        target_type="user",
        target_id=user_id,
        detail={"delta": int(delta), "from": current, "to": new_balance},
    )
    if notify:
        if delta >= 0:
            text = f"💎 مبلغ {int(delta):,} تومان به کیف پول شما اضافه شد.\nموجودی جدید: {new_balance:,} تومان"
        else:
            text = f"➖ مبلغ {abs(int(delta)):,} تومان از کیف پول شما کسر شد.\nموجودی جدید: {new_balance:,} تومان"
        await notify_user(user_id, text)
    return new_balance


async def set_user_block(ctx: PanelActor, user_id: int, blocked: bool, *, notify: bool = True) -> bool:
    async with Session() as session:
        result = await session.execute(update(User).where(User.id == user_id).values(status="ban" if blocked else None))
        await session.commit()
        changed = bool(result.rowcount)
    if not changed:
        return False
    await _audit(ctx, "user_block" if blocked else "user_unblock", target_type="user", target_id=user_id)
    if notify:
        await notify_user(
            user_id,
            "⛔️ دسترسی شما به ربات مسدود شد." if blocked else "✅ حساب شما از حالت مسدود خارج شد.",
        )
    return True


async def set_user_phone(ctx: PanelActor, user_id: int, phone: str | None) -> bool:
    """Store a normalised phone number, or clear it when ``phone`` is None.

    The number is what the browser login checks against, so an admin who has
    only ever reached the bot through Telegram needs a way to record one.
    """
    async with Session() as session:
        result = await session.execute(update(User).where(User.id == user_id).values(number=phone))
        await session.commit()
        if not result.rowcount:
            return False
    await _audit(
        ctx,
        "user_phone_set" if phone else "user_phone_clear",
        target_type="user",
        target_id=user_id,
    )
    return True


async def send_user_message(ctx: PanelActor, user_id: int, text: str) -> None:
    await notify_user(user_id, f"📥 پیام از مدیریت:\n\n{text}")
    await _audit(ctx, "user_message", target_type="user", target_id=user_id, detail={"length": len(text)})


# --------------------------------------------------------------------------- #
#  Services                                                                     #
# --------------------------------------------------------------------------- #


async def set_service_enabled(ctx: PanelActor, code: int, enabled: bool) -> bool:
    async with Session() as session:
        result = await session.execute(update(Service).where(Service.code == code).values(enable=enabled))
        await session.commit()
    if not result.rowcount:
        return False
    await _audit(ctx, "service_enable" if enabled else "service_disable", target_type="service", target_id=code)
    return True


async def delete_service_row(ctx: PanelActor, code: int) -> bool:
    async with Session() as session:
        result = await session.execute(delete(Service).where(Service.code == code))
        await session.commit()
    if not result.rowcount:
        return False
    await _audit(ctx, "service_delete", target_type="service", target_id=code)
    return True


# --------------------------------------------------------------------------- #
#  Transactions                                                                 #
# --------------------------------------------------------------------------- #


async def approve_transaction(ctx: PanelActor, tx_id: int) -> bool:
    """Approve a pending transaction through the bot's own flow (bonus included)."""
    async with Session() as session:
        tx = (await session.execute(select(Transaction).where(Transaction.id == tx_id))).scalars().first()
        if tx is None or tx.status != "pending":
            return False
        user_id = int(tx.user_id)
        amount = int(tx.amount or 0)

    settings = await SettingsManager().get_settings()
    result = await TransactionCRUD().approve_manual(tx)
    if result is None:
        return False

    bonus = int(result.get("bonus") or 0)
    total = int(result.get("total") or 0)
    await _audit(
        ctx,
        "tx_approve",
        target_type="transaction",
        target_id=tx_id,
        detail={"amount": amount, "bonus": bonus},
    )
    bonus_line = (
        f"🎁 بونوس: +{bonus:,} ({settings.manual_bonus_percent}%)\n💰 مجموع: {total:,} تومان\n" if bonus > 0 else ""
    )
    template = await get_bot_text(key="manual_card_approved_message", default=TX_APPROVED_USER_MESSAGE, lang="fa")
    message = template.format(user_id=user_id, amount=f"{amount:,}", bonus_line=bonus_line)
    await notify_user(user_id, message)
    return True


async def reject_transaction(ctx: PanelActor, tx_id: int) -> bool:
    async with Session() as session:
        tx = (await session.execute(select(Transaction).where(Transaction.id == tx_id))).scalars().first()
        if tx is None or tx.status != "pending":
            return False
        tx.status = "rejected"
        tx.completed_at = int(time.time())
        user_id = int(tx.user_id)
        amount = int(tx.amount or 0)
        await session.commit()

    await ManualAutoApproveRuleCRUD.cancel_schedule(tx_id)
    await _audit(ctx, "tx_reject", target_type="transaction", target_id=tx_id, detail={"amount": amount})
    template = await get_bot_text(key="manual_card_rejected_message", default=TX_REJECTED_USER_MESSAGE, lang="fa")
    await notify_user(user_id, template.format(amount=f"{amount:,}"))
    return True


async def request_receipt_fix_transaction(ctx: PanelActor, tx_id: int) -> bool:
    """Ask the user to re-enter the amount and resend the receipt (bot's ♻️ button)."""
    async with Session() as session:
        tx = (await session.execute(select(Transaction).where(Transaction.id == tx_id))).scalars().first()
        if tx is None or tx.status != "pending":
            return False
        tx.status = "needs_fix"
        tx.completed_at = int(time.time())
        tx.auto_approve_at = None
        tx.auto_approve_rule_id = None
        user_id = int(tx.user_id)
        amount = int(tx.amount or 0)
        await session.commit()

    await ManualAutoApproveRuleCRUD.cancel_schedule(tx_id)
    await ReceiptHashCRUD().delete_by_transaction_id(tx_id)
    await _audit(ctx, "tx_request_fix", target_type="transaction", target_id=tx_id, detail={"amount": amount})

    current_cards = await ManualCardManager().get_all_cards()
    current_card = next((card for card in current_cards if card.active), None)
    template = await get_bot_text(key="manual_card_receipt_fix_message", default=TX_RECEIPT_FIX_USER_MESSAGE, lang="fa")
    message = template.format(
        amount=f"{amount:,}",
        amount_toman=f"{amount:,}",
        amount_rial=f"{amount * 10:,}",
        current_card_name=getattr(current_card, "name", "") or CARD_HOLDER_NOT_SET,
        current_card_number=getattr(current_card, "number", "") or CARD_HOLDER_NOT_SET,
    )
    await notify_user(user_id, message)
    return True


async def report_card_mismatch_transaction(ctx: PanelActor, tx_id: int) -> bool:
    """Tell the user their deposit card doesn't match (bot's 💳 button). Status stays pending."""
    async with Session() as session:
        tx = (await session.execute(select(Transaction).where(Transaction.id == tx_id))).scalars().first()
        if tx is None or tx.status != "pending":
            return False
        user_id = int(tx.user_id)
        amount = int(tx.amount or 0)

    await _audit(ctx, "tx_card_mismatch", target_type="transaction", target_id=tx_id, detail={"amount": amount})

    current_cards = await ManualCardManager().get_all_cards()
    current_card = next((card for card in current_cards if card.active), None)
    template = await get_bot_text(
        key="manual_card_card_mismatch_message", default=TX_CARD_MISMATCH_USER_MESSAGE, lang="fa"
    )
    message = template.format(
        current_card_name=getattr(current_card, "name", "") or CARD_HOLDER_NOT_SET,
        current_card_number=getattr(current_card, "number", "") or CARD_HOLDER_NOT_SET,
        amount=f"{amount:,}",
        amount_toman=f"{amount:,}",
        amount_rial=f"{amount * 10:,}",
    )
    await notify_user(user_id, message)
    return True


# --------------------------------------------------------------------------- #
#  Panels                                                                       #
# --------------------------------------------------------------------------- #


async def upsert_panel(ctx: PanelActor, code: int | None, values: dict[str, Any]) -> int:
    """Create or update a panel row. Returns the panel code.

    ``values`` may include legacy flat fields (e.g. ``test_enabled``) that live
    inside a JSON column; ``resolve_panel_update_kwargs`` maps those onto the
    real columns the same way the bot's own panel editors do.
    """
    async with Session() as session:
        if code is None:
            highest = (await session.execute(select(Panels.code).order_by(Panels.code.desc()).limit(1))).scalar()
            new_code = int(highest or 0) + 1
            session.add(Panels(code=new_code, **resolve_panel_update_kwargs(None, **values)))
            await session.commit()
            await _audit(
                ctx, "panel_create", target_type="panel", target_id=new_code, detail={"name": values.get("name")}
            )
            return new_code
        panel = (await session.execute(select(Panels).where(Panels.code == code))).scalars().first()
        resolved = resolve_panel_update_kwargs(panel, **values)
        await session.execute(update(Panels).where(Panels.code == code).values(**resolved))
        await session.commit()
    await _audit(ctx, "panel_update", target_type="panel", target_id=code, detail={"fields": sorted(values)})
    return code


async def delete_panel(ctx: PanelActor, code: int) -> bool:
    async with Session() as session:
        result = await session.execute(delete(Panels).where(Panels.code == code))
        await session.commit()
    if not result.rowcount:
        return False
    await _audit(ctx, "panel_delete", target_type="panel", target_id=code)
    return True


# --------------------------------------------------------------------------- #
#  Plans                                                                        #
# --------------------------------------------------------------------------- #


async def upsert_plan(ctx: PanelActor, plan_id: int | None, values: dict[str, Any]) -> int:
    async with Session() as session:
        if plan_id is None:
            plan = Plan(**values)
            session.add(plan)
            await session.commit()
            await session.refresh(plan)
            new_id = int(plan.id)
            await _audit(ctx, "plan_create", target_type="plan", target_id=new_id, detail=values)
            return new_id
        await session.execute(update(Plan).where(Plan.id == plan_id).values(**values))
        await session.commit()
    await _audit(ctx, "plan_update", target_type="plan", target_id=plan_id, detail=values)
    return plan_id


async def delete_plan(ctx: PanelActor, plan_id: int) -> bool:
    async with Session() as session:
        result = await session.execute(delete(Plan).where(Plan.id == plan_id))
        await session.commit()
    if not result.rowcount:
        return False
    await _audit(ctx, "plan_delete", target_type="plan", target_id=plan_id)
    return True


# --------------------------------------------------------------------------- #
#  Resellers                                                                    #
# --------------------------------------------------------------------------- #


async def update_reseller(ctx: PanelActor, code: int, values: dict[str, Any]) -> bool:
    async with Session() as session:
        result = await session.execute(update(ResellerAccount).where(ResellerAccount.code == code).values(**values))
        await session.commit()
    if not result.rowcount:
        return False
    await _audit(ctx, "reseller_update", target_type="reseller", target_id=code, detail=values)
    return True


async def delete_reseller(ctx: PanelActor, code: int) -> bool:
    async with Session() as session:
        result = await session.execute(delete(ResellerAccount).where(ResellerAccount.code == code))
        await session.commit()
    if not result.rowcount:
        return False
    await _audit(ctx, "reseller_delete", target_type="reseller", target_id=code)
    return True


async def upsert_reseller_plan(ctx: PanelActor, plan_id: int | None, values: dict[str, Any]) -> int:
    async with Session() as session:
        if plan_id is None:
            plan = ResellerPlan(**values)
            session.add(plan)
            await session.commit()
            await session.refresh(plan)
            new_id = int(plan.id)
            await _audit(ctx, "reseller_plan_create", target_type="reseller_plan", target_id=new_id, detail=values)
            return new_id
        await session.execute(update(ResellerPlan).where(ResellerPlan.id == plan_id).values(**values))
        await session.commit()
    await _audit(ctx, "reseller_plan_update", target_type="reseller_plan", target_id=plan_id, detail=values)
    return plan_id


async def delete_reseller_plan(ctx: PanelActor, plan_id: int) -> bool:
    async with Session() as session:
        result = await session.execute(delete(ResellerPlan).where(ResellerPlan.id == plan_id))
        await session.commit()
    if not result.rowcount:
        return False
    await _audit(ctx, "reseller_plan_delete", target_type="reseller_plan", target_id=plan_id)
    return True


# --------------------------------------------------------------------------- #
#  Discount codes                                                               #
# --------------------------------------------------------------------------- #


async def upsert_discount(ctx: PanelActor, code_id: int | None, values: dict[str, Any]) -> int | None:
    async with Session() as session:
        if code_id is None:
            existing = (
                (await session.execute(select(DiscountCode).where(DiscountCode.code == values.get("code"))))
                .scalars()
                .first()
            )
            if existing is not None:
                return None
            row = DiscountCode(**values)
            session.add(row)
            await session.commit()
            await session.refresh(row)
            new_id = int(row.id)
            await _audit(ctx, "discount_create", target_type="discount", target_id=new_id, detail=values)
            return new_id
        await session.execute(update(DiscountCode).where(DiscountCode.id == code_id).values(**values))
        await session.commit()
    await _audit(ctx, "discount_update", target_type="discount", target_id=code_id, detail=values)
    return code_id


async def delete_discount(ctx: PanelActor, code_id: int) -> bool:
    async with Session() as session:
        result = await session.execute(delete(DiscountCode).where(DiscountCode.id == code_id))
        await session.commit()
    if not result.rowcount:
        return False
    await _audit(ctx, "discount_delete", target_type="discount", target_id=code_id)
    return True
