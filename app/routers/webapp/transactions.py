"""Unified payment transaction history (manual card, crypto)."""

import asyncio
from typing import Any

from fastapi import APIRouter

from app.db.crud.cryptopayments import get_user_all_crypto_transactions
from app.db.crud.ir_gateway_payments import IrGatewayPaymentCRUD
from app.db.crud.stars_transactions import StarsTransactionCRUD
from app.db.crud.tonpays_invoices import OPEN_STATUSES, TonPaysInvoiceCRUD
from app.db.crud.transactions import TransactionCRUD
from app.models.webapp import WebAppTransactionsRequest, WebAppTransactionsResponse
from app.routers.webapp.auth import authenticate_user
from app.services.payments.ir_gateways.providers import GATEWAYS

router = APIRouter()


@router.post("/webapp/transactions", response_model=WebAppTransactionsResponse)
async def get_webapp_transactions(request: WebAppTransactionsRequest) -> WebAppTransactionsResponse:
    """Get paginated user payment transactions across all payment methods."""
    try:
        user_id = await authenticate_user(init_data=request.init_data, session_token=request.session_token)
        page = request.page
        limit = request.limit

        tx_crud = TransactionCRUD()
        card_txs, crypto_txs, tonpays_txs, stars_txs, gateway_txs = await asyncio.gather(
            tx_crud.get_user_all_transactions(user_id),
            get_user_all_crypto_transactions(user_id),
            TonPaysInvoiceCRUD().list_for_user(user_id),
            StarsTransactionCRUD().get_user_all_transactions(user_id),
            IrGatewayPaymentCRUD().list_for_user(user_id),
        )

        transactions: list[dict[str, Any]] = []
        for tx in card_txs:
            transactions.append(
                {
                    "id": f"tx_{tx.id}",
                    "type_key": "manual_card",
                    "currency": None,
                    "amount": int(getattr(tx, "amount", 0) or 0),
                    "status": getattr(tx, "status", "pending") or "pending",
                    "created_at": int(getattr(tx, "created_at", 0) or 0),
                    "emoji": "💳",
                }
            )

        for tx in crypto_txs:
            crypto_status = "approved" if tx.status == "Paid" else "pending" if tx.status == "Pending" else "rejected"
            transactions.append(
                {
                    "id": f"crypto_{tx.order_id}",
                    "type_key": "crypto",
                    "currency": str(tx.arz).upper() if tx.arz else None,
                    "amount": int(getattr(tx, "amount_irt", 0) or 0),
                    "status": crypto_status,
                    "created_at": int(getattr(tx, "createtime", 0) or 0),
                    "emoji": "💰",
                }
            )

        for tx in tonpays_txs:
            tonpays_status = (
                "approved" if tx.status == "completed" else "pending" if tx.status in OPEN_STATUSES else "rejected"
            )
            transactions.append(
                {
                    "id": f"tonpays_{tx.id}",
                    "type_key": "tonpays",
                    "currency": None,
                    "amount": int(tx.amount or 0),
                    "status": tonpays_status,
                    "created_at": int(tx.created_at or 0),
                    "emoji": "💎",
                }
            )

        for tx in gateway_txs:
            provider = GATEWAYS.get(tx.gateway)
            transactions.append(
                {
                    "id": f"{tx.gateway}_{tx.id}",
                    "type_key": tx.gateway,
                    "currency": None,
                    "amount": int(tx.amount or 0),
                    "status": {"completed": "approved", "pending": "pending"}.get(tx.status, "rejected"),
                    "created_at": int(tx.created_at or 0),
                    "emoji": provider.emoji if provider else "🏦",
                }
            )

        for tx in stars_txs:
            stars_status = {"approved": "approved", "pending": "pending"}.get(tx.status, "rejected")
            transactions.append(
                {
                    "id": f"stars_{tx.id}",
                    "type_key": "stars",
                    "currency": None,
                    "amount": int(tx.amount or 0),
                    "status": stars_status,
                    "created_at": int(tx.created_at or 0),
                    "emoji": "⭐",
                }
            )

        transactions.sort(key=lambda item: item["created_at"], reverse=True)
        total = len(transactions)
        start = (page - 1) * limit
        end = start + limit
        total_pages = (total + limit - 1) // limit if limit > 0 else 0
        return WebAppTransactionsResponse(
            ok=True,
            transactions=transactions[start:end],
            total=total,
            page=page,
            limit=limit,
            total_pages=total_pages,
        )
    except ValueError as e:
        return WebAppTransactionsResponse(ok=False, error=str(e))
    except Exception as e:
        return WebAppTransactionsResponse(ok=False, error=str(e))
