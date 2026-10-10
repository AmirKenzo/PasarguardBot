"""Zibal return URL: the buyer's browser lands here after paying (or canceling) on Zibal.

The query string is never trusted; `handle_callback` re-verifies the payment with Zibal.
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from app.logger import get_logger
from app.routers.webhook.payment_page import ResultView, render_result_page, return_links
from app.services.payments.zibal import ZibalError, handle_callback, status_label

logger = get_logger(__name__)

router = APIRouter()

GATEWAY_NAME = "زیبال"


@router.get("/payments/zibal/callback", response_class=HTMLResponse)
async def zibal_callback(
    track_id: str = Query("", alias="trackId", max_length=64),
    success: str = Query("", max_length=4),
) -> HTMLResponse:
    links = await return_links()

    track_id = track_id.strip()
    if not track_id:
        return render_result_page(
            ResultView("danger", "درخواست نامعتبر", "شناسه پرداخت در این لینک وجود ندارد."), links, GATEWAY_NAME
        )
    try:
        payment = await handle_callback(track_id, success)
    except ZibalError as e:
        logger.warning("Zibal callback for %s failed: %s", track_id, e.message)
        payment = None
    except Exception:
        logger.exception("Zibal callback for %s crashed", track_id)
        payment = None

    if payment is None:
        view = ResultView(
            "danger",
            "پرداخت پیدا نشد",
            "این پرداخت در ربات ثبت نشده یا بررسی آن با خطا روبه‌رو شد.",
            note="اگر مبلغی از حساب شما کسر شده، از داخل ربات «بررسی پرداخت» را بزنید یا با پشتیبانی تماس بگیرید.",
        )
        return render_result_page(view, links, GATEWAY_NAME)

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
    return render_result_page(view, links, GATEWAY_NAME)
