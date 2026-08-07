import json
import random

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.future import select

from app.db.base import AsyncSessionLocal as Session
from app.db.models.reseller_accounts import ResellerAccount
from app.logger import get_logger
from app.utils.formatting.conversions import as_int

log = get_logger(__name__)


class ResellerAccountCRUD:
    async def create_account(self, **kwargs) -> tuple[bool, ResellerAccount | str]:
        try:
            async with Session() as session:
                account = ResellerAccount(**kwargs)
                session.add(account)
                await session.commit()
                return True, account
        except SQLAlchemyError as e:
            return False, f"Error creating reseller account: {e}"

    async def get_account(self, code) -> tuple[bool, ResellerAccount | str]:
        code = as_int(code)
        if code is None:
            return False, "Account not found."
        try:
            async with Session() as session:
                result = await session.execute(select(ResellerAccount).filter_by(code=code))
                account = result.scalars().first()
                if account:
                    return True, account
                return False, "Account not found."
        except SQLAlchemyError as e:
            return False, f"Error getting account: {e}"

    async def get_accounts_by_user(self, telegram_id: int) -> list[ResellerAccount]:
        try:
            async with Session() as session:
                result = await session.execute(
                    select(ResellerAccount)
                    .where(ResellerAccount.telegram_id == telegram_id)
                    .order_by(ResellerAccount.createtime.desc())
                )
                return list(result.scalars().all())
        except SQLAlchemyError as e:
            log.error("Failed to list user reseller accounts: %s", e)
            return []

    async def get_accounts_by_status(self, status: str) -> list[ResellerAccount]:
        try:
            async with Session() as session:
                result = await session.execute(select(ResellerAccount).where(ResellerAccount.status == status))
                return list(result.scalars().all())
        except SQLAlchemyError as e:
            log.error("Failed to list reseller accounts by status: %s", e)
            return []

    async def get_billable_accounts(self, pricing_modes: tuple[str, ...]) -> list[ResellerAccount]:
        try:
            async with Session() as session:
                result = await session.execute(
                    select(ResellerAccount).where(
                        ResellerAccount.pricing_mode.in_(pricing_modes),
                        ResellerAccount.status == "active",
                    )
                )
                return list(result.scalars().all())
        except SQLAlchemyError as e:
            log.error("Failed to list billable reseller accounts: %s", e)
            return []

    async def get_accounts_to_expire(self, now: int) -> list[ResellerAccount]:
        try:
            async with Session() as session:
                result = await session.execute(
                    select(ResellerAccount).where(
                        ResellerAccount.expiration_time.is_not(None),
                        ResellerAccount.expiration_time <= now,
                        ResellerAccount.status.in_(("active", "suspended", "paused")),
                    )
                )
                return list(result.scalars().all())
        except SQLAlchemyError as e:
            log.error("Failed to list expiring reseller accounts: %s", e)
            return []

    async def get_accounts_for_grace_deletion(self, grace_before: int) -> list[ResellerAccount]:
        try:
            async with Session() as session:
                result = await session.execute(
                    select(ResellerAccount).where(
                        ResellerAccount.expiration_time.is_not(None),
                        ResellerAccount.expiration_time <= grace_before,
                        ResellerAccount.status == "expired",
                    )
                )
                return list(result.scalars().all())
        except SQLAlchemyError as e:
            log.error("Failed to list grace-deletion reseller accounts: %s", e)
            return []

    async def get_accounts_by_plan(self, plan_id: int) -> list[ResellerAccount]:
        plan_id = as_int(plan_id)
        if plan_id is None:
            return []
        try:
            async with Session() as session:
                result = await session.execute(select(ResellerAccount).where(ResellerAccount.plan_id == plan_id))
                return list(result.scalars().all())
        except SQLAlchemyError as e:
            log.error("Failed to list reseller accounts by plan: %s", e)
            return []

    async def get_by_panel_username(self, panel_code: int, username: str) -> ResellerAccount | None:
        panel_code = as_int(panel_code)
        username = (username or "").strip()
        if panel_code is None or not username:
            return None
        try:
            async with Session() as session:
                result = await session.execute(
                    select(ResellerAccount).where(
                        ResellerAccount.panel_code == panel_code,
                        ResellerAccount.username == username,
                    )
                )
                return result.scalars().first()
        except SQLAlchemyError as e:
            log.error("Failed to get reseller account by panel/username: %s", e)
            return None

    async def count_accounts_by_plan(self, plan_id: int) -> int:
        plan_id = as_int(plan_id)
        if plan_id is None:
            return 0
        try:
            async with Session() as session:
                result = await session.execute(
                    select(func.count()).select_from(ResellerAccount).where(ResellerAccount.plan_id == plan_id)
                )
                return int(result.scalar() or 0)
        except SQLAlchemyError as e:
            log.error("Failed to count reseller accounts by plan: %s", e)
            return 0

    async def delete_account(self, code) -> bool:
        code = as_int(code)
        if code is None:
            return False
        try:
            async with Session() as session:
                result = await session.execute(select(ResellerAccount).filter_by(code=code))
                account = result.scalars().first()
                if not account:
                    return False
                await session.delete(account)
                await session.commit()
                return True
        except SQLAlchemyError as e:
            log.error("Failed to delete reseller account: %s", e)
            return False

    async def update_account(self, code, **kwargs) -> bool:
        code = as_int(code)
        if code is None:
            return False
        try:
            async with Session() as session:
                result = await session.execute(select(ResellerAccount).filter_by(code=code))
                account = result.scalars().first()
                if not account:
                    return False
                for key, value in kwargs.items():
                    if hasattr(account, key):
                        setattr(account, key, value)
                await session.commit()
                return True
        except SQLAlchemyError as e:
            log.error("Failed to update reseller account: %s", e)
            return False

    async def generate_unique_code(self) -> int:
        for _ in range(20):
            code = random.randint(100000, 9999999)
            ok, _ = await self.get_account(code)
            if not ok:
                return code
        return random.randint(10000000, 99999999)

    @staticmethod
    def load_billing_state(raw: str | None) -> dict:
        if not raw:
            return {}
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except TypeError, json.JSONDecodeError:
            return {}

    @staticmethod
    def dump_billing_state(data: dict) -> str:
        return json.dumps(data or {}, ensure_ascii=False)
