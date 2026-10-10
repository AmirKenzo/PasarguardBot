"""Zarinpal return URL: the buyer's browser lands here after paying (or canceling) on Zarinpal.

The query string is never trusted; `handle_callback` re-verifies the payment with Zarinpal.
"""

from __future__ import annotations

import html

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from app import Kenzo
from app.logger import get_logger
from app.services.payments.zarinpal import ZarinpalError, handle_callback, status_label
from config import WEBAPP_URL

logger = get_logger(__name__)

router = APIRouter()

_bot_username: str | None = None


async def _bot_link() -> str | None:
    global _bot_username
    if _bot_username is None:
        try:
            me = await Kenzo.get_me()
            _bot_username = getattr(me, "username", None) or ""
        except Exception as e:
            logger.warning("Could not resolve the bot username for the Zarinpal page: %s", e)
            return None
    return f"https://t.me/{_bot_username}" if _bot_username else None


def _page(title: str, body: str, color: str, links: list[tuple[str, str]]) -> HTMLResponse:
    buttons = "".join(
        f'<a class="btn" href="{html.escape(url, quote=True)}">{html.escape(label)}</a>' for label, url in links
    )
    content = f"""<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<style>
body{{margin:0;font-family:Tahoma,Vazirmatn,sans-serif;background:#f4f5f7;color:#1f2328;
display:flex;min-height:100vh;align-items:center;justify-content:center;padding:16px;box-sizing:border-box}}
.card{{background:#fff;border-radius:16px;max-width:420px;width:100%;padding:28px 22px;text-align:center;
box-shadow:0 4px 24px rgba(0,0,0,.08)}}
h1{{font-size:20px;color:{color};margin:0 0 14px}}
p{{line-height:1.9;margin:6px 0;font-size:15px}}
.btn{{display:block;margin-top:14px;padding:12px;border-radius:10px;background:#0a7cff;color:#fff;
text-decoration:none;font-weight:bold}}
@media (prefers-color-scheme:dark){{body{{background:#121417;color:#e6e6e6}}.card{{background:#1d2024}}}}
</style></head>
<body><div class="card"><h1>{html.escape(title)}</h1>{body}{buttons}</div></body></html>"""
    return HTMLResponse(content=content)


@router.get("/payments/zarinpal/callback", response_class=HTMLResponse)
async def zarinpal_callback(
    authority: str = Query("", alias="Authority", max_length=64),
    status: str = Query("", alias="Status", max_length=8),
) -> HTMLResponse:
    links: list[tuple[str, str]] = []
    bot_link = await _bot_link()
    if bot_link:
        links.append(("بازگشت به ربات", bot_link))
    if WEBAPP_URL:
        links.append(("بازگشت به وب‌اپ", WEBAPP_URL))

    authority = authority.strip()
    if not authority:
        return _page("درخواست نامعتبر", "<p>شناسه پرداخت ارسال نشده است.</p>", "#d1242f", links)
    try:
        payment = await handle_callback(authority, status)
    except ZarinpalError as e:
        logger.warning("Zarinpal callback for %s failed: %s", authority, e.message)
        payment = None
    except Exception:
        logger.exception("Zarinpal callback for %s crashed", authority)
        payment = None
    if payment is None:
        return _page(
            "پرداخت پیدا نشد",
            "<p>این پرداخت در ربات ثبت نشده یا بررسی آن با خطا روبه‌رو شد.</p>"
            "<p>اگر مبلغ از حساب شما کسر شده، از داخل ربات «بررسی پرداخت» را بزنید یا با پشتیبانی تماس بگیرید.</p>",
            "#d1242f",
            links,
        )

    amount = f"{int(payment.amount):,}"
    if payment.status == "completed":
        body = (
            f"<p>مبلغ <b>{amount}</b> تومان به کیف پول شما اضافه شد.</p>"
            f"<p>کد پیگیری: <b>{html.escape(payment.ref_id or '—')}</b></p>"
        )
        if payment.sandbox:
            body += "<p>🧪 این یک پرداخت تستی (sandbox) بود.</p>"
        return _page("✅ پرداخت موفق", body, "#1a7f37", links)
    if payment.status == "pending":
        return _page(
            "⏳ در انتظار تأیید",
            "<p>پرداخت هنوز تأیید نشده است. چند لحظه بعد از داخل ربات «بررسی پرداخت» را بزنید.</p>",
            "#9a6700",
            links,
        )
    return _page(
        f"❌ {status_label(payment.status)}",
        f"<p>پرداخت {amount} تومانی انجام نشد.</p>"
        "<p>اگر مبلغی از حساب شما کسر شده، حداکثر تا ۷۲ ساعت به حساب‌تان برمی‌گردد.</p>",
        "#d1242f",
        links,
    )
