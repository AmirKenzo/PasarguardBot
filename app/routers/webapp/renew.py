"""Manual renewal: options discovery and paid confirmation (locked per service)."""

from fastapi import APIRouter
from pasarguard import PasarguardAPI

from app.db.crud.discount_codes import DiscountCodeManager
from app.db.crud.panels import PanelsManager
from app.db.crud.plans import PlanManager
from app.db.crud.services import ServiceCRUD
from app.db.crud.user import UserCRUD
from app.logger import get_logger
from app.models.webapp import (
    RenewPlanItem,
    WebAppRenewConfirmRequest,
    WebAppRenewConfirmResponse,
    WebAppRenewOptionsRequest,
    WebAppRenewOptionsResponse,
)
from app.routers.webapp.auth import authenticate_user
from app.routers.webapp.state import renew_confirm_locks
from app.services.billing.renewal import PaidRenewalError, execute_paid_service_renewal, require_panel_userid
from app.utils.formatting.conversions import convert_storage
from app.utils.formatting.traffic import format_size

logger = get_logger(__name__)
router = APIRouter()


def _group_durations(durations: list[int]) -> dict[str, list[int]]:
    """Return duration groups for display: e.g. {'7 روزه': [7], '30 روزه': [30]}."""
    return {f"{d} روزه": [d] for d in sorted(durations)}


@router.post("/webapp/renew/options", response_model=WebAppRenewOptionsResponse)
async def get_renew_options(request: WebAppRenewOptionsRequest) -> WebAppRenewOptionsResponse:
    """Get renewal options (durations and plans) for a service."""

    try:
        user_id = await authenticate_user(
            init_data=request.init_data,
            session_token=request.session_token,
        )
        service_crud = ServiceCRUD()
        found, service = await service_crud.get_service(request.code)
        if not found or not service or int(service.id) != user_id:
            return WebAppRenewOptionsResponse(ok=False, error="سرویس یافت نشد")
        if getattr(service, "is_test", False) is True:
            return WebAppRenewOptionsResponse(ok=False, error="سرویس‌های تست قابل تمدید نیستند")

        panel = await PanelsManager().get_panel_by_code(service.in_panel)
        if not panel:
            return WebAppRenewOptionsResponse(ok=False, error="پنل یافت نشد")

        panel_name = getattr(panel, "name", None) or "پنل"
        durations = await PlanManager().get_unique_durations(service.in_panel)
        duration_groups = _group_durations(durations) if durations else {}

        plans = await PlanManager().get_all_plans(panel_code=service.in_panel)
        is_fair_usage = False
        if service.package_size:
            current_plan = await PlanManager().get_plan_by_volume_for_display(
                gb=float(service.package_size) / (1024**3), panel_code=service.in_panel
            )
            if current_plan and getattr(current_plan, "plan_type", None) in ("fair_usage", "fair"):
                is_fair_usage = True

        if is_fair_usage:
            filtered_plans = [p for p in plans if getattr(p, "plan_type", None) in ("fair_usage", "fair")]
        else:
            filtered_plans = [
                p for p in plans if getattr(p, "plan_type", None) != "fair_usage" or not hasattr(p, "plan_type")
            ]

        if not filtered_plans:
            return WebAppRenewOptionsResponse(ok=False, error="هیچ پلنی برای تمدید یافت نشد")

        sorted_plans = sorted(filtered_plans, key=lambda p: p.storage)
        plan_items = []
        for p in sorted_plans:
            plan_name = convert_storage(
                float(p.storage),
                getattr(p, "plan_type", None),
                getattr(p, "data_limit_reset_strategy", None),
                for_button=True,
            )
            plan_items.append(
                RenewPlanItem(
                    id=p.id,
                    storage=float(p.storage),
                    duration=int(p.duration),
                    price=int(p.price),
                    plan_name=plan_name,
                    ip_limit=int(getattr(p, "ip_limit", 0) or 0),
                )
            )

        return WebAppRenewOptionsResponse(
            ok=True,
            service_code=str(request.code),
            panel_name=panel_name,
            is_fair_usage=is_fair_usage,
            durations=durations,
            duration_groups=duration_groups,
            plans=plan_items,
        )
    except ValueError as e:
        return WebAppRenewOptionsResponse(ok=False, error=str(e))
    except Exception as e:
        return WebAppRenewOptionsResponse(ok=False, error=str(e))


@router.post("/webapp/renew/confirm", response_model=WebAppRenewConfirmResponse)
async def confirm_renew(request: WebAppRenewConfirmRequest) -> WebAppRenewConfirmResponse:
    """Confirm renewal: deduct balance, apply discount if provided, update service."""

    async with renew_confirm_locks[int(request.code)]:
        return await _confirm_renew_locked(request)


async def _confirm_renew_locked(request: WebAppRenewConfirmRequest) -> WebAppRenewConfirmResponse:
    try:
        user_id = await authenticate_user(
            init_data=request.init_data,
            session_token=request.session_token,
        )
        service_crud = ServiceCRUD()
        found, serv_msg = await service_crud.get_service(request.code)
        if not found or not serv_msg or int(serv_msg.id) != user_id:
            return WebAppRenewConfirmResponse(ok=False, error="سرویس یافت نشد")
        if getattr(serv_msg, "is_test", False) is True:
            return WebAppRenewConfirmResponse(ok=False, error="سرویس‌های تست قابل تمدید نیستند")

        plan = await PlanManager().get_plan(request.plan_id)
        if not plan or int(plan.panel_code) != int(serv_msg.in_panel):
            return WebAppRenewConfirmResponse(ok=False, error="پلن یافت نشد")

        price = int(plan.price)
        if request.discount_code and request.discount_code.strip():
            status, res = await DiscountCodeManager().validate_discount_code(
                code=request.discount_code.strip(), user_id=user_id
            )
            if not status:
                return WebAppRenewConfirmResponse(ok=False, error=str(res) if res else "کد تخفیف نامعتبر است")
            if status and res and hasattr(res, "discount_percentage"):
                pct = int(res.discount_percentage or 0)
                price = max(0, int(plan.price) - (int(plan.price) * pct // 100))

        user = await UserCRUD().read_user(user_id)
        balance = int(user.amount or 0)
        if balance < price:
            return WebAppRenewConfirmResponse(
                ok=False,
                error="موجودی کیف پول کافی نیست. لطفاً ابتدا موجودی خود را افزایش دهید.",
            )

        panel = await PanelsManager().get_panel_by_code(serv_msg.in_panel)
        if not panel:
            return WebAppRenewConfirmResponse(ok=False, error="پنل یافت نشد")

        try:
            get_User = await PasarguardAPI(panel.base_url).get_user_by_id(
                user_id=require_panel_userid(serv_msg), token=panel.cookie
            )
        except Exception:
            return WebAppRenewConfirmResponse(ok=False, error="خطا در ارتباط با پنل")

        try:
            new_hajm, new_balance = await execute_paid_service_renewal(
                serv_msg,
                panel,
                plan,
                price=price,
                panel_user=get_User,
            )
        except PaidRenewalError as exc:
            return WebAppRenewConfirmResponse(ok=False, error=str(exc))
        except Exception:
            logger.exception("renew panel/db failed for service=%s", request.code)
            return WebAppRenewConfirmResponse(
                ok=False,
                error="خطا در اعمال تمدید روی پنل. موجودی به کیف پول بازگردانده شد.",
            )

        if request.discount_code and request.discount_code.strip():
            await DiscountCodeManager().update_discount_usage(request.discount_code.strip())

        new_volume_str = format_size(new_hajm, decimal_places=0)
        return WebAppRenewConfirmResponse(
            ok=True,
            message="تمدید با موفقیت انجام شد.",
            new_balance=new_balance,
            new_volume=new_volume_str,
            amount_paid=price,
            config_name=serv_msg.username,
        )
    except ValueError as e:
        return WebAppRenewConfirmResponse(ok=False, error=str(e))
    except Exception as e:
        logger.exception("renew confirm failed for service=%s: %s", request.code, e)
        return WebAppRenewConfirmResponse(ok=False, error="خطا در تمدید سرویس")
