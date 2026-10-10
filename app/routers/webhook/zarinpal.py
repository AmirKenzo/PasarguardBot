"""Zarinpal return URL: the buyer's browser lands here after paying (or canceling) on Zarinpal.

The query string is never trusted; `handle_callback` re-verifies the payment with Zarinpal.
"""

from __future__ import annotations

import html
from dataclasses import dataclass, field
from typing import Literal

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from app import Kenzo
from app.logger import get_logger
from app.services.payments.zarinpal import ZarinpalError, handle_callback, status_label
from config import WEBAPP_URL

logger = get_logger(__name__)

router = APIRouter()

Tone = Literal["success", "warning", "danger"]

_bot_username: str | None = None

_ICONS: dict[Tone, str] = {
    "success": '<path d="M20 6 9 17l-5-5"/>',
    "warning": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "danger": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
}

_STYLE = """
:root{--bg:244 245 249;--surface:255 255 255;--text:16 19 28;--muted:100 106 124;--border:15 23 42;
--primary:59 130 246;--success:22 163 74;--warning:217 119 6;--danger:220 38 38;color-scheme:light}
@media (prefers-color-scheme:dark){:root{--bg:10 12 20;--surface:19 21 34;--text:241 242 247;--muted:150 156 176;
--border:255 255 255;--primary:96 165 250;--success:74 222 128;--warning:251 191 36;--danger:248 113 113;
color-scheme:dark}}
*{box-sizing:border-box;margin:0;padding:0}
body{min-height:100vh;min-height:100dvh;display:flex;align-items:center;justify-content:center;padding:24px 16px;
font-family:"Estedad",Tahoma,system-ui,sans-serif;background:rgb(var(--bg));color:rgb(var(--text));
background-image:radial-gradient(circle at 50% 0,rgb(var(--tone)/.14),transparent 60%)}
.card{width:100%;max-width:400px;background:rgb(var(--surface));border:1px solid rgb(var(--border)/.08);
border-radius:24px;padding:32px 22px 22px;text-align:center;box-shadow:0 20px 50px -20px rgb(0 0 0/.25);
animation:rise .45s cubic-bezier(.2,.8,.2,1) both}
.icon{width:76px;height:76px;margin:0 auto 18px;border-radius:50%;display:grid;place-items:center;
background:rgb(var(--tone)/.12);box-shadow:0 0 0 8px rgb(var(--tone)/.06);animation:pop .5s .15s both}
.icon svg{width:38px;height:38px;stroke:rgb(var(--tone));fill:none;stroke-width:2.6;stroke-linecap:round;
stroke-linejoin:round}
h1{font-size:20px;font-weight:800;margin-bottom:8px}
.lead{font-size:14px;line-height:1.9;color:rgb(var(--muted))}
.amount{margin:20px 0 4px;font-size:30px;font-weight:800;letter-spacing:-.5px;color:rgb(var(--tone))}
.amount small{font-size:14px;font-weight:500;color:rgb(var(--muted));margin-inline-start:4px}
.badge{display:inline-block;margin-top:12px;padding:4px 12px;border-radius:999px;font-size:12px;font-weight:600;
background:rgb(var(--primary)/.12);color:rgb(var(--primary))}
.details{margin:22px 0 4px;border:1px solid rgb(var(--border)/.08);border-radius:16px;overflow:hidden;text-align:start}
.row{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 14px;font-size:13px}
.row+.row{border-top:1px dashed rgb(var(--border)/.1)}
.row span{color:rgb(var(--muted))}
.row b{font-weight:600;direction:ltr;unicode-bidi:plaintext;display:flex;align-items:center;gap:8px}
.copy{border:0;cursor:pointer;font:inherit;font-size:11px;padding:3px 8px;border-radius:8px;
background:rgb(var(--primary)/.1);color:rgb(var(--primary))}
.note{margin-top:16px;padding:12px;border-radius:14px;font-size:12px;line-height:1.9;text-align:start;
background:rgb(var(--warning)/.1);color:rgb(var(--warning))}
.actions{display:grid;gap:10px;margin-top:22px}
.btn{display:block;padding:14px;border-radius:14px;font-size:15px;font-weight:700;text-decoration:none;
transition:transform .15s,opacity .15s}
.btn:active{transform:scale(.98)}
.btn-primary{background:rgb(37 99 235);color:#fff;box-shadow:0 8px 20px -8px rgb(37 99 235/.7)}
.btn-ghost{background:rgb(var(--border)/.05);color:rgb(var(--text))}
.foot{margin-top:18px;font-size:11px;color:rgb(var(--muted));display:flex;align-items:center;justify-content:center;
gap:6px}
.foot svg{width:13px;height:13px;stroke:currentColor;fill:none;stroke-width:2}
@keyframes rise{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:none}}
@keyframes pop{from{opacity:0;transform:scale(.6)}to{opacity:1;transform:none}}
@media (prefers-reduced-motion:reduce){.card,.icon{animation:none}}
"""

_SCRIPT = """
document.querySelectorAll('[data-copy]').forEach(function(b){b.addEventListener('click',function(){
var v=b.getAttribute('data-copy');var done=function(){var t=b.textContent;b.textContent='کپی شد ✓';
setTimeout(function(){b.textContent=t},1500)};
if(navigator.clipboard){navigator.clipboard.writeText(v).then(done)}else{var i=document.createElement('input');
i.value=v;document.body.appendChild(i);i.select();document.execCommand('copy');i.remove();done()}})});
"""


@dataclass
class _View:
    tone: Tone
    title: str
    lead: str
    amount: int | None = None
    rows: list[tuple[str, str, bool]] = field(default_factory=list)  # (label, value, copyable)
    note: str | None = None
    sandbox: bool = False
    retry: bool = False


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


def _render(view: _View, links: list[tuple[str, str]]) -> HTMLResponse:
    esc = html.escape
    tone_var = {"success": "var(--success)", "warning": "var(--warning)", "danger": "var(--danger)"}[view.tone]
    amount = f'<p class="amount">{view.amount:,}<small>تومان</small></p>' if view.amount is not None else ""
    badge = '<span class="badge">🧪 پرداخت تستی (Sandbox)</span>' if view.sandbox else ""
    rows = "".join(
        f'<div class="row"><span>{esc(label)}</span><b>{esc(value)}'
        + (f'<button class="copy" type="button" data-copy="{esc(value, quote=True)}">کپی</button>' if copy else "")
        + "</b></div>"
        for label, value, copy in view.rows
    )
    details = f'<div class="details">{rows}</div>' if rows else ""
    note = f'<p class="note">{esc(view.note)}</p>' if view.note else ""
    buttons = []
    if view.retry:
        buttons.append('<a class="btn btn-primary" href="">بررسی دوباره</a>')
    for index, (label, url) in enumerate(links):
        style = "btn-primary" if index == 0 and not view.retry else "btn-ghost"
        buttons.append(f'<a class="btn {style}" href="{esc(url, quote=True)}">{esc(label)}</a>')
    content = f"""<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex">
<title>{esc(view.title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Estedad:wght@400;500;600;700;800&display=swap"
 rel="stylesheet" media="print" onload="this.media='all'">
<style>:root{{--tone:{tone_var}}}{_STYLE}</style></head>
<body><main class="card">
<div class="icon"><svg viewBox="0 0 24 24" aria-hidden="true">{_ICONS[view.tone]}</svg></div>
<h1>{esc(view.title)}</h1><p class="lead">{esc(view.lead)}</p>
{amount}{badge}{details}{note}
<div class="actions">{"".join(buttons)}</div>
<p class="foot"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="11" width="14" height="10" rx="2"/>
<path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>پرداخت امن از طریق درگاه زرین‌پال</p>
</main><script>{_SCRIPT}</script></body></html>"""
    return HTMLResponse(content=content, headers={"Cache-Control": "no-store"})


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
        return _render(_View("danger", "درخواست نامعتبر", "شناسه پرداخت در این لینک وجود ندارد."), links)
    try:
        payment = await handle_callback(authority, status)
    except ZarinpalError as e:
        logger.warning("Zarinpal callback for %s failed: %s", authority, e.message)
        payment = None
    except Exception:
        logger.exception("Zarinpal callback for %s crashed", authority)
        payment = None

    if payment is None:
        view = _View(
            "danger",
            "پرداخت پیدا نشد",
            "این پرداخت در ربات ثبت نشده یا بررسی آن با خطا روبه‌رو شد.",
            note="اگر مبلغی از حساب شما کسر شده، از داخل ربات «بررسی پرداخت» را بزنید یا با پشتیبانی تماس بگیرید.",
        )
        return _render(view, links)

    order_row = ("شناسه سفارش", payment.order_id, True)
    if payment.status == "completed":
        rows = [("کد پیگیری", payment.ref_id or "—", bool(payment.ref_id)), order_row]
        if payment.card_pan:
            rows.append(("کارت پرداخت‌کننده", payment.card_pan, False))
        view = _View(
            "success",
            "پرداخت با موفقیت انجام شد",
            "موجودی کیف پول شما شارژ شد. می‌توانید به ربات برگردید.",
            amount=int(payment.amount),
            rows=rows,
            sandbox=payment.sandbox,
        )
    elif payment.status == "pending":
        view = _View(
            "warning",
            "در انتظار تأیید پرداخت",
            "پرداخت هنوز از سمت بانک تأیید نشده است. چند لحظه بعد دوباره بررسی کنید.",
            amount=int(payment.amount),
            rows=[order_row],
            sandbox=payment.sandbox,
            retry=True,
        )
    else:
        view = _View(
            "danger",
            f"پرداخت {status_label(payment.status)}",
            "پرداخت انجام نشد و موجودی شما تغییری نکرد.",
            amount=int(payment.amount),
            rows=[order_row],
            note="اگر مبلغی از حساب شما کسر شده، طبق قوانین بانکی حداکثر تا ۷۲ ساعت به حساب‌تان برمی‌گردد.",
            sandbox=payment.sandbox,
        )
    return _render(view, links)
