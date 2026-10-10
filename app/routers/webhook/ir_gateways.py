"""Return URL for every Iranian direct gateway: /api/payments/<gateway>/callback.

The buyer's browser lands here after paying (or canceling). The query string is never trusted:
`handle_callback` re-verifies the payment with the gateway before anything is credited.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.logger import get_logger
from app.routers.webhook.payment_page import ResultView, render_result_page, return_links
from app.services.payments.ir_gateways.providers import GATEWAYS, GatewayError
from app.services.payments.ir_gateways.service import handle_callback, status_label

logger = get_logger(__name__)

router = APIRouter()

_MAX_PARAM_LENGTH = 128


@router.get("/payments/{gateway}/callback", response_class=HTMLResponse)
async def ir_gateway_callback(gateway: str, request: Request) -> HTMLResponse:
    provider = GATEWAYS.get(gateway)
    if provider is None:
        raise HTTPException(status_code=404, detail="Unknown gateway")
    query = {key: value[:_MAX_PARAM_LENGTH] for key, value in request.query_params.items()}
    links = await return_links()

    authority, _ = provider.parse_callback(query)
    if not authority:
        view = ResultView("danger", "درخواست نامعتبر", "شناسه پرداخت در این لینک وجود ندارد.")
        return render_result_page(view, links, provider.title)
    try:
        payment = await handle_callback(gateway, query)
    except GatewayError as e:
        logger.warning("%s callback for %s failed: %s", gateway, authority, e.message)
        payment = None
    except Exception:
        logger.exception("%s callback for %s crashed", gateway, authority)
        payment = None

    if payment is None:
        view = ResultView(
            "danger",
            "پرداخت پیدا نشد",
            "این پرداخت در ربات ثبت نشده یا بررسی آن با خطا روبه‌رو شد.",
            note="اگر مبلغی از حساب شما کسر شده، از داخل ربات «بررسی پرداخت» را بزنید یا با پشتیبانی تماس بگیرید.",
        )
        return render_result_page(view, links, provider.title)

    order_row = ("شناسه سفارش", payment.order_id, True)
    if payment.status == "completed":
        rows = [("کد پیگیری", payment.ref_id or "—", bool(payment.ref_id)), order_row]
        if payment.card_pan:
            rows.append(("کارت پرداخت‌کننده", payment.card_pan, False))
        view = ResultView(
            "success",
            "پرداخت با موفقیت انجام شد",
            "موجودی کیف پول شما شارژ شد. می‌توانید به ربات برگردید.",
            amount=int(payment.amount),
            rows=rows,
            sandbox=payment.sandbox,
        )
    elif payment.status == "pending":
        view = ResultView(
            "warning",
            "در انتظار تأیید پرداخت",
            "پرداخت هنوز از سمت بانک تأیید نشده است. چند لحظه بعد دوباره بررسی کنید.",
            amount=int(payment.amount),
            rows=[order_row],
            sandbox=payment.sandbox,
            retry=True,
        )
    else:
        view = ResultView(
            "danger",
            f"پرداخت {status_label(payment.status)}",
            "پرداخت انجام نشد و موجودی شما تغییری نکرد.",
            amount=int(payment.amount),
            rows=[order_row],
            note="اگر مبلغی از حساب شما کسر شده، طبق قوانین بانکی حداکثر تا ۷۲ ساعت به حساب‌تان برمی‌گردد.",
            sandbox=payment.sandbox,
        )
    return render_result_page(view, links, provider.title)
