"""TonPays top-up from the web app: create, check, change card, upload receipt."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile

from app.db.crud.tonpays_invoices import OPEN_STATUSES, TonPaysInvoiceCRUD
from app.db.models.tonpays_invoice import TonPaysInvoice
from app.logger import get_logger
from app.models.webapp import (
    BalanceTonPaysDepositRequest,
    BalanceTonPaysInvoiceRequest,
    BalanceTonPaysInvoiceResponse,
    BalanceTonPaysOpenRequest,
    TonPaysInvoiceView,
)
from app.routers.webapp.auth import authenticate_user
from app.services.payments.tonpays import (
    TonPaysError,
    change_card,
    create_deposit,
    refresh_invoice,
    status_label,
    submit_receipt,
)

logger = get_logger(__name__)
router = APIRouter()

_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic", ".heif")


def _view(invoice: TonPaysInvoice) -> TonPaysInvoiceView:
    return TonPaysInvoiceView(
        id=int(invoice.id),
        invoice_id=invoice.invoice_id,
        mode=invoice.mode,
        amount=int(invoice.amount),
        final_amount=int(invoice.final_amount) if invoice.final_amount else None,
        status=invoice.status,
        status_label=status_label(invoice.status),
        invoice_url=invoice.invoice_url,
        web_invoice_url=invoice.web_invoice_url,
        card_number=invoice.card_number,
        card_name=invoice.card_name,
        receipt_sent=bool(invoice.receipt_sent),
    )


async def _owned(user_id: int, local_id: int) -> TonPaysInvoice:
    invoice = await TonPaysInvoiceCRUD().get_for_user(local_id, user_id)
    if not invoice:
        raise TonPaysError("فاکتور پیدا نشد.")
    return invoice


@router.post("/webapp/balance/deposit/tonpays", response_model=BalanceTonPaysInvoiceResponse)
async def deposit_tonpays(request: BalanceTonPaysDepositRequest) -> BalanceTonPaysInvoiceResponse:
    try:
        user_id = await authenticate_user(init_data=request.init_data, session_token=request.session_token)
        invoice = await create_deposit(user_id, request.amount, source="webapp")
        return BalanceTonPaysInvoiceResponse(ok=True, message="فاکتور ساخته شد.", invoice=_view(invoice))
    except (TonPaysError, ValueError) as e:
        return BalanceTonPaysInvoiceResponse(ok=False, error=getattr(e, "message", None) or str(e))
    except Exception:
        logger.exception("TonPays deposit failed")
        return BalanceTonPaysInvoiceResponse(ok=False, error="خطا در ساخت فاکتور TonPays.")


@router.post("/webapp/balance/tonpays/open", response_model=BalanceTonPaysInvoiceResponse)
async def latest_open_tonpays(request: BalanceTonPaysOpenRequest) -> BalanceTonPaysInvoiceResponse:
    """The caller's newest open invoice, so the page can resume after a reload."""
    try:
        user_id = await authenticate_user(init_data=request.init_data, session_token=request.session_token)
        invoices = await TonPaysInvoiceCRUD().list_for_user(user_id)
        latest = next((inv for inv in invoices if inv.status in OPEN_STATUSES), None)
        return BalanceTonPaysInvoiceResponse(ok=True, invoice=_view(latest) if latest else None)
    except ValueError as e:
        return BalanceTonPaysInvoiceResponse(ok=False, error=str(e))


@router.post("/webapp/balance/tonpays/status", response_model=BalanceTonPaysInvoiceResponse)
async def tonpays_status(request: BalanceTonPaysInvoiceRequest) -> BalanceTonPaysInvoiceResponse:
    try:
        user_id = await authenticate_user(init_data=request.init_data, session_token=request.session_token)
        invoice = await refresh_invoice(await _owned(user_id, request.invoice))
        return BalanceTonPaysInvoiceResponse(ok=True, invoice=_view(invoice))
    except (TonPaysError, ValueError) as e:
        return BalanceTonPaysInvoiceResponse(ok=False, error=getattr(e, "message", None) or str(e))


@router.post("/webapp/balance/tonpays/change-card", response_model=BalanceTonPaysInvoiceResponse)
async def tonpays_change_card(request: BalanceTonPaysInvoiceRequest) -> BalanceTonPaysInvoiceResponse:
    try:
        user_id = await authenticate_user(init_data=request.init_data, session_token=request.session_token)
        invoice = await _owned(user_id, request.invoice)
        data = await change_card(invoice)
        invoice = await TonPaysInvoiceCRUD().get(invoice.id) or invoice
        message = "کارت دیگری برای تعویض موجود نیست." if data.get("change_card_exhausted") else "کارت تعویض شد."
        return BalanceTonPaysInvoiceResponse(ok=True, message=message, invoice=_view(invoice))
    except (TonPaysError, ValueError) as e:
        return BalanceTonPaysInvoiceResponse(ok=False, error=getattr(e, "message", None) or str(e))


@router.post("/webapp/balance/tonpays/receipt", response_model=BalanceTonPaysInvoiceResponse)
async def tonpays_receipt(
    invoice: int = Form(...),
    session_token: str | None = Form(None),
    init_data: str | None = Form(None),
    file: UploadFile = File(...),
) -> BalanceTonPaysInvoiceResponse:
    try:
        user_id = await authenticate_user(init_data=init_data, session_token=session_token)
        row = await _owned(user_id, invoice)
        filename = file.filename or "receipt.jpg"
        content_type = (file.content_type or "").lower()
        if not content_type.startswith("image/") and not filename.lower().endswith(_IMAGE_EXTENSIONS):
            return BalanceTonPaysInvoiceResponse(ok=False, error="فایل باید تصویر باشد (JPG, PNG, ...)")
        row = await submit_receipt(row, await file.read(), filename, content_type or "image/jpeg")
        return BalanceTonPaysInvoiceResponse(ok=True, message="فیش ارسال شد و در انتظار تأیید است.", invoice=_view(row))
    except (TonPaysError, ValueError) as e:
        return BalanceTonPaysInvoiceResponse(ok=False, error=getattr(e, "message", None) or str(e))
