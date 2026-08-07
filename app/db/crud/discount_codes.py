from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import desc, func, select, update
from sqlalchemy.exc import IntegrityError

from app.db.base import AsyncSessionLocal as Session
from app.db.models.discount_codes import DiscountCode
from app.logger import get_logger
from app.services.billing.sticky_discount import clear_sticky_for_code

log = get_logger(__name__)


class DiscountCodeManager:
    async def create_discount_code(
        self,
        code,
        discount_percentage,
        is_public=None,
        user_id=None,
        expiration_days=30,
        expiration_seconds=None,
        usage_limit=1,
    ):
        """Create a new discount code."""
        code = (code or "").strip().upper()
        log.debug("Creating discount code: %s with percentage: %s", code, discount_percentage)

        async with Session() as session:
            result = await session.execute(select(DiscountCode).filter_by(code=code))
            existing_code = result.scalar()
            if existing_code:
                log.warning("Discount code %s already exists; cannot create duplicate.", code)
                return None

        if is_public and is_public.lower() == "false":
            is_public = False
        elif is_public and is_public.lower() == "true":
            is_public = True

        if expiration_seconds is not None:
            expiration_date = int(datetime.now().timestamp()) + int(expiration_seconds)
        else:
            expiration_date = int((datetime.now() + timedelta(days=expiration_days)).timestamp())
        new_code = DiscountCode(
            code=code,
            discount_percentage=discount_percentage,
            is_public=bool(is_public),
            user_id=user_id,
            expiration_date=expiration_date,
            usage_limit=usage_limit,
        )

        try:
            async with Session() as session:
                session.add(new_code)
                await session.commit()
                log.info("Discount code %s created successfully.", code)
                return True

        except IntegrityError as e:
            log.error("Integrity error while creating discount code: %s", e)
            return None
        except Exception as e:
            log.error("Failed to create discount code: %s", e)
            return None

    async def extend_discount(self, code: str, *, seconds: int) -> bool:
        """Extend a discount code expiration by the given number of seconds."""
        if seconds <= 0:
            return False
        try:
            async with Session() as session:
                result = await session.execute(select(DiscountCode).filter_by(code=code))
                discount_code = result.scalar()
                if not discount_code:
                    log.debug("Discount code not found code=%s", code)
                    return False
                discount_code.expiration_date += int(seconds)
                await session.commit()
                log.debug("Discount code extended code=%s seconds=%s", code, seconds)
                return True
        except Exception as e:
            log.error("Discount code extension failed: %s", e)
            return False

    async def tamdid_discount_30day(self, code):
        """Extend a discount code expiration by 30 days."""
        return await self.extend_discount(code, seconds=86400 * 30)

    async def update_discount_usage(self, code):
        """Increment the usage counter for a discount code."""
        try:
            async with Session() as session:
                result = await session.execute(
                    update(DiscountCode)
                    .where(DiscountCode.code == code)
                    .values(times_used=func.coalesce(DiscountCode.times_used, 0) + 1)
                    .returning(DiscountCode.times_used, DiscountCode.usage_limit)
                )
                row = result.first()
                if row is None:
                    log.debug("Discount code not found code=%s", code)
                    return
                await session.commit()
                times_used, usage_limit = row
                if usage_limit is not None and times_used is not None and times_used >= usage_limit:
                    await clear_sticky_for_code(code)
                log.debug("Discount usage updated code=%s", code)

        except Exception as e:
            log.error("Discount usage update failed: %s", e)

    async def get_code_whith_user_id(self, user_id):
        """Return the discount code assigned to a user, if any."""
        try:
            async with Session() as session:
                result = await session.execute(select(DiscountCode).filter_by(user_id=user_id))
                discount_code = result.scalar()
                if discount_code:
                    return discount_code
                return False

        except Exception as e:
            log.warning("Discount code lookup failed: %s", e)
            return False

    async def validate_discount_code(self, code, user_id=None):
        """Validate a discount code for the given user."""
        try:
            async with Session() as session:
                result = await session.execute(select(DiscountCode).filter_by(code=code))
                discount_code = result.scalar()

                if not discount_code:
                    return False, "کد تخفیف یافت نشد."

                if discount_code.expiration_date and discount_code.expiration_date < int(datetime.now().timestamp()):
                    return False, "کد تخفیف منقضی شده است."

                if discount_code.times_used >= discount_code.usage_limit:
                    return False, "تعداد دفعات استفاده از این کد تخفیف تمام شده است."

                if not discount_code.is_public and discount_code.user_id != user_id:
                    return False, "این کد تخفیف برای شما معتبر نیست."

                return True, discount_code

        except Exception as e:
            log.warning("Discount code lookup failed: %s", e)
            return False, "خطا در بررسی کد تخفیف"

    async def discount_get_by_code(self, code):
        """Fetch a discount code by its code string."""
        try:
            async with Session() as session:
                result = await session.execute(select(DiscountCode).filter_by(code=code))
                discount_code = result.scalar()
                if discount_code:
                    return discount_code

        except Exception as e:
            log.warning("Discount code lookup failed: %s", e)
            return False

    async def delete_discount_code(self, code):
        """Delete a discount code by its code string."""
        try:
            async with Session() as session:
                result = await session.execute(select(DiscountCode).filter_by(code=code))
                discount_code = result.scalar()

                if discount_code:
                    code_value = discount_code.code
                    await session.delete(discount_code)
                    await session.commit()
                    await clear_sticky_for_code(code_value)
                    return True, discount_code
                return False, "کد تخفیف مورد نظر پیدا نشد."

        except Exception as e:
            log.error("Discount code delete failed: %s", e)
            return False, f"خطا در حذف کد تخفیف: {e}"

    async def get_all_discount_codes(self):
        """Return all discount codes, newest first."""
        try:
            async with Session() as session:
                stmt = select(DiscountCode).order_by(desc(DiscountCode.created_at))
                result = await session.execute(stmt)
                return result.scalars().all()
        except Exception:
            log.exception("Failed to fetch discount code list:")
            return []

    async def get_discount_statistics(self) -> dict[str, Any]:
        """Aggregate discount-code metrics for the admin stats panel."""
        codes = await self.get_all_discount_codes()
        now = int(datetime.now().timestamp())
        soon_threshold = int((datetime.now() + timedelta(days=7)).timestamp())

        stats: dict[str, Any] = {
            "total": len(codes),
            "active": 0,
            "inactive": 0,
            "expired": 0,
            "exhausted": 0,
            "expiring_soon": 0,
            "public": 0,
            "private": 0,
            "never_used": 0,
            "with_usage": 0,
            "total_uses": 0,
            "total_capacity": 0,
            "remaining_uses": 0,
            "avg_percent": 0.0,
            "usage_rate": 0.0,
            "most_used": None,
            "top_used": [],
            "highest_percent": None,
            "newest_code": None,
            "oldest_code": None,
        }

        if not codes:
            return stats

        percents: list[int] = []
        top_candidates: list[DiscountCode] = []

        for code in codes:
            times_used = int(code.times_used or 0)
            usage_limit = int(code.usage_limit or 0)
            is_expired = bool(code.expiration_date and code.expiration_date < now)
            is_exhausted = usage_limit > 0 and times_used >= usage_limit
            is_active = not is_expired and not is_exhausted

            if is_active:
                stats["active"] += 1
            else:
                stats["inactive"] += 1
            if is_expired:
                stats["expired"] += 1
            if is_exhausted:
                stats["exhausted"] += 1
            if code.expiration_date and not is_expired and code.expiration_date <= soon_threshold:
                stats["expiring_soon"] += 1
            if code.is_public:
                stats["public"] += 1
            else:
                stats["private"] += 1
            if times_used == 0:
                stats["never_used"] += 1
            else:
                stats["with_usage"] += 1
                top_candidates.append(code)

            stats["total_uses"] += times_used
            stats["total_capacity"] += usage_limit
            stats["remaining_uses"] += max(usage_limit - times_used, 0)
            percents.append(int(code.discount_percentage or 0))

        stats["avg_percent"] = round(sum(percents) / len(percents), 1)
        if stats["total_capacity"] > 0:
            stats["usage_rate"] = round((stats["total_uses"] / stats["total_capacity"]) * 100, 1)

        if top_candidates:
            top_candidates.sort(key=lambda c: (int(c.times_used or 0), int(c.discount_percentage or 0)), reverse=True)
            stats["most_used"] = top_candidates[0]
            stats["top_used"] = top_candidates[:5]

        highest = max(codes, key=lambda c: int(c.discount_percentage or 0))
        stats["highest_percent"] = highest
        stats["newest_code"] = codes[0]
        stats["oldest_code"] = codes[-1]
        return stats

    async def reset_times_used(self, code: str) -> bool:
        """Reset the usage counter for a discount code to zero."""
        try:
            async with Session() as session:
                result = await session.execute(select(DiscountCode).filter_by(code=code))
                discount_code = result.scalar()
                if not discount_code:
                    return False
                discount_code.times_used = 0
                await session.commit()
                return True
        except Exception as e:
            log.error("Discount usage reset failed: %s", e)
            return False

    async def rename_discount_code(self, old_code: str, new_code: str) -> tuple[bool, str]:
        """Rename a discount code. Returns (success, new_code_or_error_message)."""
        new_code = (new_code or "").strip().upper()
        if not new_code:
            return False, "Invalid new code."
        try:
            async with Session() as session:
                result = await session.execute(select(DiscountCode).filter_by(code=old_code))
                discount_code = result.scalar()
                if not discount_code:
                    return False, "Discount code not found."

                exists = await session.execute(select(DiscountCode).filter_by(code=new_code))
                if exists.scalar() and new_code != old_code:
                    return False, "This code is already taken."

                discount_code.code = new_code
                await session.commit()
                await clear_sticky_for_code(old_code)
                return True, new_code
        except IntegrityError:
            return False, "This code is already taken."
        except Exception as e:
            log.error("Discount code rename failed: %s", e)
            return False, "Failed to rename discount code."

    async def update_discount_fields(self, code: str, **fields) -> bool:
        """Update one or more fields on a discount code."""
        if not fields:
            return False
        try:
            async with Session() as session:
                result = await session.execute(select(DiscountCode).filter_by(code=code))
                discount_code = result.scalar()
                if not discount_code:
                    return False
                for key, value in fields.items():
                    if hasattr(discount_code, key):
                        setattr(discount_code, key, value)
                await session.commit()
                return True
        except Exception as e:
            log.error("Discount code update failed: %s", e)
            return False
