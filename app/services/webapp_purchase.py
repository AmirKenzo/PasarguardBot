import asyncio
import random
import re
import time
from dataclasses import dataclass
from typing import Any

from httpx import HTTPStatusError
from pasarguard import GroupsResponse, PasarguardAPI, UserCreate
from pasarguard.enums import UserDataLimitResetStrategy

from app import Kenzo
from app.db.crud.discount_codes import DiscountCodeManager
from app.db.crud.panels import PanelsManager
from app.db.crud.plans import PlanManager
from app.db.crud.services import ServiceCRUD
from app.db.crud.settings import SettingsManager
from app.db.crud.user import UserCRUD, debit_Money_if_sufficient, update_Money
from app.logger import LogType, get_logger
from app.services.panels.config_links import get_selected_single_config_links_text
from app.services.panels.nodes import filter_nodes_by_plan_type, format_node_name_for_display
from app.services.panels.settings import panel_default_group_ids, panel_display_mode
from app.services.public_report import send_purchase_report
from app.services.send_queue import enqueue
from app.services.subscriptions.links import format_subscription_links_for_message
from app.services.users.identifiers import generate_username
from app.utils.formatting.conversions import convert_storage, day_to_timestamp, gigabytes_to_bytes
from app.utils.formatting.dates import Time_Date
from app.utils.formatting.traffic import format_ip_limit

logger = get_logger(__name__)

USERNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_]{1,30}[A-Za-z0-9]$")
PANEL_USERNAME_CONFLICT_CODES = frozenset((400, 409, 422))


@dataclass(slots=True)
class PricePreview:
    base_price: int
    final_price: int
    discount_percent: int = 0
    discount_code: str | None = None


def is_valid_config_username(name: str) -> bool:
    return bool(USERNAME_RE.fullmatch((name or "").strip()))


def resolve_panel_group_ids(panel: Any, groups_resp: GroupsResponse) -> list[int]:
    selected_ids = sorted(panel_default_group_ids(panel))
    if selected_ids:
        return selected_ids

    groups = getattr(groups_resp, "groups", None) or []
    return [int(group.id) for group in groups if getattr(group, "id", None) is not None]


def is_panel_username_conflict(exc: BaseException) -> bool:
    return isinstance(exc, HTTPStatusError) and exc.response.status_code in PANEL_USERNAME_CONFLICT_CODES


async def process_referral_reward_payout(referrer_id: int, referred_id: int) -> None:
    try:
        from app.db.crud.referral import ReferralManager

        referral_manager = ReferralManager()
        settings = await referral_manager.get_referral_settings()
        if not settings or not settings.referral_enabled:
            return

        ok, _reason = await referral_manager.process_referral_reward(referrer_id, referred_id)
        if not ok:
            return

        await Kenzo.send_message(
            referrer_id,
            f"🎉 تبریک! شما {settings.referral_reward_amount:,} تومان پاداش دعوت دریافت کردید!\n\n"
            f"👤 کاربر خریدار: {referred_id}\n"
            f"💰 مبلغ پاداش: {settings.referral_reward_amount:,} تومان\n"
            f"🎁 مبلغ هدیه کاربر: {settings.referral_bonus_amount:,} تومان",
        )
    except Exception as e:
        logger.error("Error processing referral reward payout: %s", e)


class WebAppPurchaseService:
    def __init__(self) -> None:
        self.panels = PanelsManager()
        self.plans = PlanManager()
        self.settings = SettingsManager()
        self.users = UserCRUD()
        self.services = ServiceCRUD()
        self.discounts = DiscountCodeManager()

    async def get_buy_options(self) -> dict[str, Any]:
        settings = await self.settings.get_settings()
        if settings and not getattr(settings, "sale_mode", True):
            return {"ok": False, "error": "فروش در حال حاضر غیرفعال است."}

        panels = await self.panels.get_available_panels()
        durations_by_panel = await self.plans.get_unique_durations_for_panels([panel.code for panel in panels])
        panel_items = []
        for panel in panels:
            durations = durations_by_panel.get(int(panel.code), [])
            panel_items.append(
                {
                    "code": int(panel.code),
                    "name": panel.name,
                    "display_mode": panel_display_mode(panel),
                    "durations": [int(d) for d in durations],
                }
            )

        return {
            "ok": True,
            "single_panel_buy_mode": bool(getattr(settings, "single_panel_buy_mode", False)) if settings else False,
            "panels": panel_items,
        }

    async def get_panel_plans(self, panel_code: int, duration: int | None = None) -> dict[str, Any]:
        panel = await self.panels.get_panel_by_code(panel_code)
        if not panel or not getattr(panel, "enable", False):
            return {"ok": False, "error": "پنل یافت نشد یا غیرفعال است."}
        if await self.panels.is_panel_at_capacity(panel_code):
            return {"ok": False, "error": "ظرفیت این پنل تکمیل شده است."}

        durations = await self.plans.get_unique_durations(panel_code)
        plans = await self.plans.get_all_plans(panel_code=panel_code, duration=duration)
        plans = sorted(plans, key=lambda p: (int(p.duration), float(p.storage), int(p.price)))

        return {
            "ok": True,
            "panel": {
                "code": int(panel.code),
                "name": panel.name,
                "display_mode": panel_display_mode(panel),
            },
            "durations": [int(d) for d in durations],
            "plans": [self._plan_item(plan) for plan in plans],
        }

    async def generate_username(self, panel_code: int) -> dict[str, Any]:
        panel = await self.panels.get_panel_by_code(panel_code)
        if not panel:
            return {"ok": False, "error": "پنل یافت نشد"}

        for _ in range(8):
            username = generate_username()
            try:
                await PasarguardAPI(panel.base_url).get_user_by_username(username=username, token=panel.cookie)
            except HTTPStatusError as e:
                if e.response.status_code == 404:
                    return {"ok": True, "username": username}
            except Exception:
                return {"ok": True, "username": username}

        return {"ok": True, "username": f"VPN{random.randint(100000, 999999)}"}

    async def preview_purchase(
        self,
        *,
        user_id: int,
        panel_code: int,
        plan_id: int,
        username: str,
        discount_code: str | None = None,
    ) -> dict[str, Any]:
        panel, plan = await self._get_panel_plan(panel_code, plan_id)
        if not is_valid_config_username(username):
            return {"ok": False, "error": "نام کانفیگ باید ۳ تا ۳۲ کاراکتر و فقط شامل حروف انگلیسی، عدد و زیرخط باشد."}

        username_error, price, user, locations = await asyncio.gather(
            self._check_username_available(panel, username),
            self._calculate_price(user_id, int(plan.price), discount_code),
            self.users.read_user(user_id),
            self._get_plan_locations(panel, plan),
        )
        if username_error:
            return {"ok": False, "error": username_error}

        balance = int(getattr(user, "amount", 0) or 0) if user else 0

        return {
            "ok": True,
            "panel_name": panel.name,
            "plan": self._plan_item(plan),
            "username": username,
            "base_price": price.base_price,
            "final_price": price.final_price,
            "discount_percent": price.discount_percent,
            "balance": balance,
            "balance_after": balance - price.final_price,
            "can_pay": balance >= price.final_price,
            "locations": locations,
        }

    async def confirm_purchase(
        self,
        *,
        user_id: int,
        panel_code: int,
        plan_id: int,
        username: str,
        discount_code: str | None = None,
    ) -> dict[str, Any]:
        panel, plan = await self._get_panel_plan(panel_code, plan_id)
        if not is_valid_config_username(username):
            return {"ok": False, "error": "نام کانفیگ نامعتبر است."}

        username_error = await self._check_username_available(panel, username)
        if username_error:
            return {"ok": False, "error": username_error}

        price = await self._calculate_price(user_id, int(plan.price), discount_code)
        user = await self.users.read_user(user_id)
        balance = int(getattr(user, "amount", 0) or 0) if user else 0
        if balance < price.final_price:
            return {"ok": False, "error": "موجودی کیف پول کافی نیست. ابتدا موجودی خود را افزایش دهید."}

        code = await self._generate_service_code()
        api = PasarguardAPI(panel.base_url)
        groups_resp: GroupsResponse = await api.get_all_groups(panel.cookie)
        group_ids = resolve_panel_group_ids(panel, groups_resp)
        reset_strategy = UserDataLimitResetStrategy.NO_RESET
        if getattr(plan, "plan_type", None) in ("fair_usage", "fair") and getattr(
            plan, "data_limit_reset_strategy", None
        ):
            reset_strategy = UserDataLimitResetStrategy(plan.data_limit_reset_strategy)

        start_time = time.time()
        new_user = UserCreate(
            username=username,
            group_ids=group_ids,
            data_limit=gigabytes_to_bytes(float(plan.storage)),
            expire=day_to_timestamp(int(plan.duration)),
            note=f"{user_id}",
            data_limit_reset_strategy=reset_strategy,
        )
        try:
            added_user = await api.add_user(user=new_user, token=panel.cookie)
        except Exception as e:
            if is_panel_username_conflict(e):
                return {"ok": False, "error": "این نام کانفیگ قبلاً در پنل ساخته شده است."}
            raise

        creation_time = time.time() - start_time
        subscription_url = added_user.subscription_url
        if subscription_url and not subscription_url.startswith("http"):
            subscription_url = f"{panel.base_url}{subscription_url}"
        links_text, primary_url = format_subscription_links_for_message(
            panel,
            subscription_url,
            main_label="🔗 لینک سابسکریپشن",
            tunnel_label="🌐 لینک تانل سابسکریپشن",
        )
        panel_userid = getattr(added_user, "id", None)
        single_links_text = await get_selected_single_config_links_text(panel, panel_userid)
        new_balance = await debit_Money_if_sufficient(user_id=user_id, amount=price.final_price)
        if new_balance is None:
            if panel_userid is not None:
                try:
                    await api.remove_user_by_id(user_id=panel_userid, token=panel.cookie)
                except Exception as cleanup_error:
                    logger.error("Failed to cleanup panel user after insufficient balance: %s", cleanup_error)
            return {"ok": False, "error": "موجودی کیف پول کافی نیست. ابتدا موجودی خود را افزایش دهید."}

        service_ok, service_msg = await self.services.create_service(
            code=code,
            username=username,
            enable=1,
            in_panel=panel.code,
            panel_userid=panel_userid,
            id=user_id,
            package_size=gigabytes_to_bytes(float(plan.storage)),
            createtime=Time_Date()["stamp"],
            expiration_time=day_to_timestamp(int(plan.duration)),
            data_limit_reset_strategy=getattr(plan, "data_limit_reset_strategy", None) or "no_reset",
            ip_limit=getattr(plan, "ip_limit", 0) or 0,
            is_test=False,
        )
        if not service_ok:
            await update_Money(user_id=user_id, Money=int(price.final_price))
            if panel_userid is not None:
                try:
                    await api.remove_user_by_id(user_id=panel_userid, token=panel.cookie)
                except Exception as cleanup_error:
                    logger.error("Failed to cleanup panel user after DB service failure: %s", cleanup_error)
            logger.error(
                "WebApp purchase rolled back after service create failure user=%s panel_user=%s error=%s",
                user_id,
                panel_userid,
                service_msg,
            )
            return {"ok": False, "error": "ثبت سرویس در دیتابیس ناموفق بود. مبلغ به کیف پول برگشت."}

        if price.discount_code:
            await self.discounts.update_discount_usage(price.discount_code)

        try:
            fresh_user = await self.users.read_user(user_id)
            if fresh_user and getattr(fresh_user, "ref", None):
                await process_referral_reward_payout(int(fresh_user.ref), user_id)
        except Exception as e:
            logger.error("Error processing referral reward: %s", e)

        volume_text = convert_storage(
            float(plan.storage),
            getattr(plan, "plan_type", None),
            getattr(plan, "data_limit_reset_strategy", None),
        )
        log_text = (
            f"📢 **خرید جدید از وب‌اپ**\n\n"
            f"👤 شناسه کاربر: `{user_id}`\n"
            f"📅 تاریخ خرید (میلادی): `{Time_Date()['mf']}`\n"
            f"📅 تاریخ خرید (شمسی): `{Time_Date()['jf']}`\n"
            f"🎫 کد سرویس: `{code}`\n"
            f"**🔷 اسم کانفیگ:** `{username}`\n"
            f"📏 حجم خریداری شده: {volume_text}\n"
            f"**🔌 محدودیت کاربر:** {format_ip_limit(getattr(plan, 'ip_limit', 0))}\n"
            f"💸 مبلغ پرداخت شده: `{price.final_price:,}` تومان\n"
            f"💵 موجودی جدید کاربر: `{new_balance:,}` تومان\n"
            f"🔗 لینک کانفیگ:\n{links_text}"
        )
        if price.discount_code:
            log_text += f"\n🎫 کد تخفیف: `{price.discount_code}`"
        await enqueue(message=log_text, log_type=LogType.OTHER)

        await send_purchase_report(
            user_id=user_id,
            panel_name=panel.name,
            plan_label=f"{int(plan.duration)} روزه",
            service_label=volume_text,
            price=price.final_price,
        )

        return {
            "ok": True,
            "service_code": code,
            "username": username,
            "panel_name": panel.name,
            "volume_bytes": gigabytes_to_bytes(float(plan.storage)),
            "duration": int(plan.duration),
            "ip_limit": int(getattr(plan, "ip_limit", 0) or 0),
            "subscription_url": primary_url,
            "subscription_links_text": links_text,
            "single_config_links_text": single_links_text or None,
            "amount_paid": price.final_price,
            "new_balance": new_balance,
            "creation_time_ms": int(creation_time * 1000),
        }

    def _plan_item(self, plan: Any) -> dict[str, Any]:
        return {
            "id": int(plan.id),
            "storage": float(plan.storage),
            "duration": int(plan.duration),
            "price": int(plan.price),
            "plan_type": getattr(plan, "plan_type", "volume"),
            "data_limit_reset_strategy": getattr(plan, "data_limit_reset_strategy", "no_reset"),
            "ip_limit": int(getattr(plan, "ip_limit", 0) or 0),
        }

    async def _get_panel_plan(self, panel_code: int, plan_id: int) -> tuple[Any, Any]:
        panel = await self.panels.get_panel_by_code(panel_code)
        if not panel or not getattr(panel, "enable", False):
            raise ValueError("پنل یافت نشد یا غیرفعال است.")
        if await self.panels.is_panel_at_capacity(panel_code):
            raise ValueError("ظرفیت این پنل تکمیل شده است.")
        plan = await self.plans.get_plan(plan_id)
        if not plan or int(plan.panel_code) != int(panel_code):
            raise ValueError("پلن یافت نشد.")
        return panel, plan

    async def _check_username_available(self, panel: Any, username: str) -> str | None:
        try:
            await PasarguardAPI(panel.base_url).get_user_by_username(username=username, token=panel.cookie)
            return "این نام کانفیگ قبلاً در پنل ساخته شده است."
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            return "خطا در بررسی نام کانفیگ در پنل."
        except Exception:
            return None

    async def _calculate_price(self, user_id: int, base_price: int, discount_code: str | None) -> PricePreview:
        code = (discount_code or "").strip()
        if not code:
            return PricePreview(base_price=base_price, final_price=base_price)

        status, result = await self.discounts.validate_discount_code(code=code, user_id=user_id)
        if not status:
            raise ValueError(str(result) if result else "کد تخفیف نامعتبر است.")

        percent = int(getattr(result, "discount_percentage", 0) or 0)
        final_price = max(0, base_price - (base_price * percent // 100))
        return PricePreview(
            base_price=base_price,
            final_price=final_price,
            discount_percent=percent,
            discount_code=code,
        )

    async def _generate_service_code(self) -> int:
        for _ in range(20):
            code = random.randint(10000, 9999999)
            found, _ = await self.services.get_service(code)
            if not found:
                return code
        raise ValueError("خطا در ساخت کد سرویس؛ دوباره تلاش کنید.")

    async def _get_plan_locations(self, panel: Any, plan: Any) -> list[str]:
        try:
            nodes_stats = await PasarguardAPI(base_url=panel.base_url).get_nodes(token=panel.cookie)
            filtered_nodes = filter_nodes_by_plan_type(nodes_stats.nodes, plan, panel)
            return [
                format_node_name_for_display(node.name, panel) for node in filtered_nodes if getattr(node, "name", None)
            ]
        except Exception:
            return []
