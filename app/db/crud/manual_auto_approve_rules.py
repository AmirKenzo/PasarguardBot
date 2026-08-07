import time
from datetime import datetime

from sqlalchemy import func, select, update

from app import Kenzo
from app.db.base import AsyncSessionLocal as Session
from app.db.crud.settings import SettingsManager
from app.db.crud.transactions import TransactionCRUD
from app.db.crud.user import UserCRUD
from app.db.models.manual_auto_approve_rule import ManualAutoApproveRule
from app.db.models.transaction import Transaction


def _format_review_duration(seconds: int) -> str:
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds} ثانیه"
    minutes, secs = divmod(seconds, 60)
    if minutes < 60:
        if secs:
            return f"{minutes} دقیقه و {secs} ثانیه"
        return f"{minutes} دقیقه"
    hours, minutes = divmod(minutes, 60)
    if minutes:
        return f"{hours} ساعت و {minutes} دقیقه"
    return f"{hours} ساعت"


def _rule_range(rule: ManualAutoApproveRule) -> str:
    max_label = str(rule.max_successful_tx) if rule.max_successful_tx is not None else "∞"
    return f"{rule.min_successful_tx}–{max_label}"


def _count_matches(rule: ManualAutoApproveRule, count: int) -> bool:
    if count < rule.min_successful_tx:
        return False
    return not (rule.max_successful_tx is not None and count > rule.max_successful_tx)


class ManualAutoApproveRuleCRUD:
    async def get_all(self, active_only: bool = False) -> list[ManualAutoApproveRule]:
        async with Session() as session:
            stmt = select(ManualAutoApproveRule).order_by(
                ManualAutoApproveRule.sort_order.asc(),
                ManualAutoApproveRule.id.asc(),
            )
            if active_only:
                stmt = stmt.where(ManualAutoApproveRule.is_active.is_(True))
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get(self, rule_id: int) -> ManualAutoApproveRule | None:
        async with Session() as session:
            result = await session.execute(select(ManualAutoApproveRule).where(ManualAutoApproveRule.id == rule_id))
            return result.scalar_one_or_none()

    async def create(
        self,
        *,
        min_successful_tx: int,
        max_successful_tx: int | None,
        auto_approve_delay_minutes: int,
        is_active: bool = True,
        sort_order: int | None = None,
    ) -> ManualAutoApproveRule:
        async with Session() as session:
            if sort_order is None:
                max_order = await session.execute(select(func.max(ManualAutoApproveRule.sort_order)))
                sort_order = (max_order.scalar() or 0) + 1
            rule = ManualAutoApproveRule(
                min_successful_tx=min_successful_tx,
                max_successful_tx=max_successful_tx,
                auto_approve_delay_minutes=auto_approve_delay_minutes,
                is_active=is_active,
                sort_order=sort_order,
            )
            session.add(rule)
            await session.commit()
            return rule

    async def update(self, rule_id: int, **kwargs) -> ManualAutoApproveRule | None:
        async with Session() as session:
            result = await session.execute(select(ManualAutoApproveRule).where(ManualAutoApproveRule.id == rule_id))
            rule = result.scalar_one_or_none()
            if not rule:
                return None
            for key, value in kwargs.items():
                if hasattr(rule, key):
                    setattr(rule, key, value)
            await session.commit()
            return rule

    async def delete(self, rule_id: int) -> bool:
        async with Session() as session:
            result = await session.execute(select(ManualAutoApproveRule).where(ManualAutoApproveRule.id == rule_id))
            rule = result.scalar_one_or_none()
            if not rule:
                return False
            await session.delete(rule)
            await session.commit()
            return True

    async def swap_sort_order(self, rule_id_a: int, rule_id_b: int) -> bool:
        async with Session() as session:
            result = await session.execute(
                select(ManualAutoApproveRule).where(ManualAutoApproveRule.id.in_([rule_id_a, rule_id_b]))
            )
            rules = {r.id: r for r in result.scalars().all()}
            if rule_id_a not in rules or rule_id_b not in rules:
                return False
            a, b = rules[rule_id_a], rules[rule_id_b]
            a.sort_order, b.sort_order = b.sort_order, a.sort_order
            await session.commit()
            return True

    async def renumber_sort_orders(self) -> None:
        rules = await self.get_all()
        async with Session() as session:
            for index, rule in enumerate(rules):
                await session.execute(
                    update(ManualAutoApproveRule).where(ManualAutoApproveRule.id == rule.id).values(sort_order=index)
                )
            await session.commit()

    async def match_for_user(self, user_id: int) -> ManualAutoApproveRule | None:
        count = await TransactionCRUD().count_user_transactions(user_id, status="approved", method="manual")
        for rule in await self.get_all(active_only=True):
            if _count_matches(rule, count):
                return rule
        return None

    async def schedule_for_transaction(self, tx: Transaction) -> ManualAutoApproveRule | None:
        settings = await SettingsManager().get_settings()
        if not settings or not settings.manual_auto_confirm:
            return None
        rule = await self.match_for_user(tx.user_id)
        if not rule or not rule.is_active or rule.auto_approve_delay_minutes <= 0:
            return rule
        approve_at = int(time.time()) + rule.auto_approve_delay_minutes * 60
        await TransactionCRUD().update(tx.id, auto_approve_at=approve_at, auto_approve_rule_id=rule.id)
        tx.auto_approve_at = approve_at
        tx.auto_approve_rule_id = rule.id
        return rule

    @staticmethod
    async def cancel_schedule(tx_id: int) -> None:
        await TransactionCRUD().update(tx_id, auto_approve_at=None, auto_approve_rule_id=None)

    @staticmethod
    def format_status_line(
        rule: ManualAutoApproveRule | None, *, auto_approve_at: int | None, successful_count: int
    ) -> str:
        if rule is None:
            return f"⏳ **تایید:** فقط دستی | 📈 تراکنش موفق: `{successful_count}`"
        if not rule.is_active or rule.auto_approve_delay_minutes <= 0:
            return f"⏳ **تایید:** فقط دستی (قانون {_rule_range(rule)})\n📈 **تراکنش موفق:** `{successful_count}`"
        if auto_approve_at:
            dt = datetime.fromtimestamp(auto_approve_at).strftime("%Y-%m-%d %H:%M")
            return (
                f"⏱ **تایید خودکار:** {rule.auto_approve_delay_minutes} دقیقه (تا {dt})\n"
                f"📈 **تراکنش موفق:** `{successful_count}` | 📋 قانون: `{_rule_range(rule)}`"
            )
        return f"⏳ **تایید:** فقط دستی | 📈 تراکنش موفق: `{successful_count}`"


async def build_manual_card_log_caption(
    *,
    user_id: int,
    amount: int,
    header: str,
    reduser=None,
    new_balance: int | None = None,
    bonus: int = 0,
    total: int | None = None,
    bonus_percent: int = 0,
    extra_line: str | None = None,
    created_at: int | None = None,
    completed_at: int | None = None,
) -> str:
    """Full manual-card log caption (same fields as receipt / admin approve)."""
    if reduser is None:
        reduser = await UserCRUD().read_user(user_id)

    crud = TransactionCRUD()
    counts = await crud.count_user_transactions_by_method_status(user_id)
    manual_approved = counts.get(("manual", "approved"), 0)
    manual_rejected = counts.get(("manual", "rejected"), 0)
    auto_approved = counts.get(("auto", "approved"), 0)
    auto_rejected = counts.get(("auto", "rejected"), 0)

    try:
        telegram_user = await Kenzo.get_entity(user_id)
        user_first_name = telegram_user.first_name or None
        user_last_name = telegram_user.last_name or None
        user_username = telegram_user.username or None
    except Exception:
        user_first_name = user_last_name = user_username = None

    user_info_parts = [f"👤 **شناسه کاربر:** `{user_id}` | [پروفایل کاربر](tg://user?id={user_id})"]
    if user_first_name or user_last_name:
        user_info_parts.append(f"✏️ **نام:** {' '.join(filter(None, [user_first_name, user_last_name]))}")
    if user_username:
        user_info_parts.append(f"📱 **یوزرنیم:** @{user_username}")
    user_info = "\n".join(user_info_parts)

    wallet_before = int(getattr(reduser, "amount", 0) or 0) if reduser else 0
    if new_balance is not None and total is not None:
        wallet_before = new_balance - total

    log_message = f"💳 #کارت_به_کارت\n{header}\n{user_info}\n"
    if created_at is not None and completed_at is not None:
        duration = _format_review_duration(completed_at - created_at)
        log_message += f"⏱ **مدت بررسی:** {duration}\n"
    if reduser and getattr(reduser, "number", None):
        log_message += f"🔢 **شماره تلفن:** {reduser.number}\n"
    log_message += f"💰 **موجودی:** `{wallet_before:,}` تومان\n"
    log_message += f"🛡️ **مبلغ وارد شده** `{int(amount):,}` تومان\n"
    if extra_line:
        log_message += f"{extra_line}\n"
    if bonus > 0:
        log_message += f"🎁 **بونوس:** +{bonus:,} تومان ({bonus_percent}%)\n"
        if total is not None:
            log_message += f"💰 **مجموع:** {total:,} تومان\n"
    if new_balance is not None:
        log_message += f"💰 **موجودی جدید:** `{new_balance:,} تومان`\n"
    log_message += (
        f"📊 **دستی:** تایید `{manual_approved:,}` | رد `{manual_rejected:,}`\n"
        f"🤖 **خودکار:** تایید `{auto_approved:,}` | رد `{auto_rejected:,}`\n"
    )
    return log_message
