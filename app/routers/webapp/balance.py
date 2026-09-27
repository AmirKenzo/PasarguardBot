"""Balance top-up methods and deposit flows: manual card, crypto and Telegram Stars."""

import random
from io import BytesIO

from fastapi import APIRouter, File, Form, UploadFile

from app import Kenzo
from app.db.crud.cards import ManualCardManager
from app.db.crud.cryptopayments import CryptoPaymentsCRUD, add_order_crypto_payment, count_pending_orders
from app.db.crud.log_channels import LogChannelManager
from app.db.crud.manual_auto_approve_rules import ManualAutoApproveRuleCRUD
from app.db.crud.settings import SettingsManager
from app.db.crud.transactions import TransactionCRUD
from app.db.crud.user import UserCRUD
from app.db.crud.wallets import WalletCRUD
from app.logger import LogType, get_logger
from app.models.webapp import (
    BalanceDepositCryptoRequest,
    BalanceDepositCryptoResponse,
    BalanceDepositManualReceiptResponse,
    BalanceDepositManualRequest,
    BalanceDepositManualResponse,
    BalanceDepositStarsRequest,
    BalanceDepositStarsResponse,
    BalanceMethodsRequest,
    BalanceMethodsResponse,
    BalancePhoneRequestRequest,
    BalancePhoneRequestResponse,
)
from app.routers.webapp.auth import authenticate_user
from app.services.pricing.crypto_amounts import (
    calculate_pol_amount_with_tax,
    calculate_ton_amount_with_tax,
    calculate_trx_amount_with_tax,
    calculate_usdt_amount_with_tax,
)
from app.services.send_queue import enqueue
from app.telegram.state import set_step
from app.telegram.user.balance import states
from app.telegram.user.balance.keyboards import transaction_review_buttons
from app.telegram.user.payment import create_star_invoice_link
from app.telegram.user.payment.helpers import STAR_USD_PRICE
from app.utils.formatting.dates import Time_Date

logger = get_logger(__name__)
router = APIRouter()


def _phone_verify_required(settings, user) -> bool:
    """Same gate as the bot: card-to-card needs a verified phone first."""
    return bool(getattr(settings, "pay_phone_verify", True)) and not (getattr(user, "number", None) if user else None)


@router.post("/webapp/balance/methods", response_model=BalanceMethodsResponse)
async def get_balance_methods(request: BalanceMethodsRequest) -> BalanceMethodsResponse:
    """Get balance top-up methods (same as bot: manual card, crypto)."""
    try:
        user_id = await authenticate_user(
            init_data=request.init_data,
            session_token=request.session_token,
        )
        settings = await SettingsManager().get_settings()
        if not settings:
            return BalanceMethodsResponse(ok=False, error="تنظیمات یافت نشد")
        user = await UserCRUD().read_user(user_id)
        phone_verify_required = _phone_verify_required(settings, user)
        card_number = None
        card_name = None
        if settings.pay_mode and not phone_verify_required:
            cards = await ManualCardManager().get_all_cards()
            if settings.manual_card_random_mode and cards:
                card = random.choice(cards)
                card_number = getattr(card, "number", None)
                card_name = getattr(card, "name", None)
            else:
                active = next((c for c in cards if getattr(c, "active", False)), None)
                if active:
                    card_number = getattr(active, "number", None)
                    card_name = getattr(active, "name", None)
        return BalanceMethodsResponse(
            ok=True,
            pay_mode=bool(settings.pay_mode),
            arz_mode=bool(settings.arz_mode),
            cart_sta=bool(getattr(settings, "cart_sta", False)),
            manual_deposit_min=int(settings.manual_deposit_min or 0),
            manual_deposit_max=int(settings.manual_deposit_max or 0),
            crypto_deposit_min=int(settings.crypto_deposit_min or 0),
            crypto_deposit_max=int(settings.crypto_deposit_max or 0),
            card_number=card_number,
            card_name=card_name,
            manual_bonus_percent=int(getattr(settings, "manual_bonus_percent", 0) or 0),
            crypto_bonus_percent=int(getattr(settings, "crypto_bonus_percent", 0) or 0),
            stars_bonus_percent=int(getattr(settings, "stars_bonus_percent", 0) or 0),
            arz_usd=int(getattr(settings, "arz_usd", 0) or 0),
            arz_trx=int(getattr(settings, "arz_trx", 0) or 0),
            arz_ton=int(getattr(settings, "arz_ton", 0) or 0),
            arz_pol=int(getattr(settings, "arz_pol", 0) or 0),
            phone_verify_required=phone_verify_required,
        )
    except ValueError as e:
        return BalanceMethodsResponse(ok=False, error=str(e))
    except Exception as e:
        return BalanceMethodsResponse(ok=False, error=str(e))


@router.post("/webapp/balance/phone/request", response_model=BalancePhoneRequestResponse)
async def request_phone_verification(request: BalancePhoneRequestRequest) -> BalancePhoneRequestResponse:
    """Arm the bot's existing contact-share step.

    The next contact this user shares with the bot (via Telegram's native
    `requestContact` WebApp prompt) gets verified and saved, same as the
    in-bot "share phone number" button.
    """
    try:
        user_id = await authenticate_user(
            init_data=request.init_data,
            session_token=request.session_token,
        )
        await set_step(user_id=user_id, step=states.STEP_CONF_NUMBER)
        return BalancePhoneRequestResponse(ok=True)
    except ValueError as e:
        return BalancePhoneRequestResponse(ok=False, error=str(e))
    except Exception as e:
        return BalancePhoneRequestResponse(ok=False, error=str(e))


@router.post("/webapp/balance/deposit/manual", response_model=BalanceDepositManualResponse)
async def deposit_manual(request: BalanceDepositManualRequest) -> BalanceDepositManualResponse:
    """Create pending manual card deposit (user pays then admin confirms or auto-confirm)."""
    try:
        user_id = await authenticate_user(
            init_data=request.init_data,
            session_token=request.session_token,
        )
        settings = await SettingsManager().get_settings()
        if not settings or not settings.pay_mode:
            return BalanceDepositManualResponse(ok=False, error="پرداخت کارت به کارت غیرفعال است")
        user = await UserCRUD().read_user(user_id)
        if _phone_verify_required(settings, user):
            return BalanceDepositManualResponse(ok=False, error="ابتدا باید شماره تلفن خود را تایید کنید.")
        amount = request.amount
        min_a = int(settings.manual_deposit_min or 0)
        max_a = int(settings.manual_deposit_max or 0)
        if amount < min_a or amount > max_a:
            return BalanceDepositManualResponse(
                ok=False,
                error=f"مبلغ باید بین {min_a:,} تا {max_a:,} تومان باشد",
            )
        cards = await ManualCardManager().get_all_cards()
        if settings.manual_card_random_mode and cards:
            active = random.choice(cards)
        else:
            active = next((c for c in cards if getattr(c, "active", False)), None)
            if not active and cards:
                active = cards[0]
        card_number = getattr(active, "number", None) if active else None
        card_name = getattr(active, "name", None) if active else None
        return BalanceDepositManualResponse(
            ok=True,
            card_number=card_number,
            card_name=card_name,
        )
    except ValueError as e:
        return BalanceDepositManualResponse(ok=False, error=str(e))
    except Exception as e:
        return BalanceDepositManualResponse(ok=False, error=str(e))


@router.post("/webapp/balance/deposit/manual/receipt", response_model=BalanceDepositManualReceiptResponse)
async def deposit_manual_receipt(
    amount: int = Form(...),
    session_token: str | None = Form(None),
    init_data: str | None = Form(None),
    file: UploadFile = File(...),
) -> BalanceDepositManualReceiptResponse:
    """Upload receipt image for a pending manual deposit; sends to log channel for approve/reject."""
    try:
        user_id = await authenticate_user(
            init_data=init_data,
            session_token=session_token,
        )
        settings = await SettingsManager().get_settings()
        if not settings or not settings.pay_mode:
            return BalanceDepositManualReceiptResponse(ok=False, error="پرداخت کارت به کارت غیرفعال است")
        user = await UserCRUD().read_user(user_id)
        if _phone_verify_required(settings, user):
            return BalanceDepositManualReceiptResponse(ok=False, error="ابتدا باید شماره تلفن خود را تایید کنید.")
        min_a = int(settings.manual_deposit_min or 0)
        max_a = int(settings.manual_deposit_max or 0)
        if amount < min_a or amount > max_a:
            return BalanceDepositManualReceiptResponse(
                ok=False,
                error=f"مبلغ باید بین {min_a:,} تا {max_a:,} تومان باشد",
            )

        filename = (file.filename or "").lower()
        content_type = (file.content_type or "").lower()
        looks_like_image = content_type.startswith("image/") or filename.endswith(
            (".jpg", ".jpeg", ".png", ".webp", ".gif", ".heic", ".heif")
        )
        if not looks_like_image:
            return BalanceDepositManualReceiptResponse(ok=False, error="فایل باید تصویر باشد (JPG, PNG, ...)")

        content = await file.read()
        if not content or len(content) > 10 * 1024 * 1024:
            return BalanceDepositManualReceiptResponse(ok=False, error="حجم تصویر حداکثر ۱۰ مگابایت باشد")

        tx = await TransactionCRUD().create(user_id=user_id, amount=amount, method="manual")
        rule_crud = ManualAutoApproveRuleCRUD()
        matched_rule = await rule_crud.schedule_for_transaction(tx)
        tx = await TransactionCRUD().get(tx.id) or tx

        user_record = await UserCRUD().read_user(user_id)
        crud = TransactionCRUD()
        manual_approved = await crud.count_user_transactions(user_id, status="approved", method="manual")
        manual_rejected = await crud.count_user_transactions(user_id, status="rejected", method="manual")
        amount = int(getattr(tx, "amount", 0))
        successful_count = manual_approved
        auto_status = rule_crud.format_status_line(
            matched_rule,
            auto_approve_at=getattr(tx, "auto_approve_at", None),
            successful_count=successful_count,
        )
        user_info = f"👤 **شناسه کاربر:** `{user_id}`"
        if user_record:
            if getattr(user_record, "number", None):
                user_info += f"\n🔢 **شماره تلفن:** {user_record.number}"
            user_info += f"\n💰 **موجودی:** `{int(getattr(user_record, 'amount', 0) or 0):,}` تومان"
        user_info += f"\n🛡️ **مبلغ واریزی:** `{amount:,}` تومان"
        user_info += f"\n{auto_status}"
        user_info += f"\n📊 **دستی:** تایید `{manual_approved}` | رد `{manual_rejected}`"
        log_message = f"💳 #کارت_به_کارت #وب‌اپ\n{user_info}"
        buttons = transaction_review_buttons(tx.id)
        target = await LogChannelManager().get_log_channel_destination(LogType.MANUAL_CARD.value)
        if target:
            chat_id, topic_id = target["chat_id"], target.get("topic_id")
            photo_buf = BytesIO(content)
            photo_buf.name = file.filename or "receipt.jpg"
            message = await Kenzo.send_file(
                chat_id,
                photo_buf,
                caption=log_message,
                buttons=buttons,
                force_document=False,
                reply_to=topic_id,
            )
            if message and getattr(message, "id", None):
                await TransactionCRUD().update(
                    tx.id,
                    message_id=message.id,
                    message_chat_id=getattr(message, "chat_id", None) or getattr(message, "peer_id", None),
                )
        return BalanceDepositManualReceiptResponse(
            ok=True,
            message="رسید ارسال شد و در انتظار تایید پشتیبانی است.",
        )
    except ValueError as e:
        return BalanceDepositManualReceiptResponse(ok=False, error=str(e))
    except Exception as e:
        return BalanceDepositManualReceiptResponse(ok=False, error=str(e))


@router.post("/webapp/balance/deposit/crypto", response_model=BalanceDepositCryptoResponse)
async def deposit_crypto(request: BalanceDepositCryptoRequest) -> BalanceDepositCryptoResponse:
    """Create crypto invoice (TRX, USDT, TON) and return wallet + amount."""
    try:
        user_id = await authenticate_user(
            init_data=request.init_data,
            session_token=request.session_token,
        )
        settings = await SettingsManager().get_settings()
        if not settings or not settings.arz_mode:
            return BalanceDepositCryptoResponse(ok=False, error="پرداخت ارزی غیرفعال است")
        currency = (request.currency or "").strip().lower()
        if currency not in ("trx", "usdt", "usdt-ton", "usdt-bep20", "ton", "pol"):
            return BalanceDepositCryptoResponse(
                ok=False, error="ارز نامعتبر. trx, usdt, usdt-ton, usdt-bep20, ton یا pol انتخاب کنید."
            )
        amount = request.amount
        min_a = int(settings.crypto_deposit_min or 0)
        max_a = int(settings.crypto_deposit_max or 0)
        if amount < min_a or amount > max_a:
            return BalanceDepositCryptoResponse(
                ok=False,
                error=f"مبلغ باید بین {min_a:,} تا {max_a:,} تومان باشد",
            )
        if await count_pending_orders(user_id) >= 3:
            return BalanceDepositCryptoResponse(
                ok=False,
                error="بیش از سه فاکتور در انتظار دارید. ابتدا فاکتورهای قبلی را پرداخت کنید.",
            )
        order_id = random.randint(55555, 999999)
        reserved = {str(p.amount) for p in await CryptoPaymentsCRUD().get_pending_by_arz(currency)}
        if currency == "trx":
            wallet = await WalletCRUD().get_wallet_by_type("TRX")
            amount_crypto = await calculate_trx_amount_with_tax(
                int(settings.arz_trx or 0), amount, reserved_amounts=reserved
            )
        elif currency == "usdt":
            wallet = await WalletCRUD().get_wallet_by_type("USDT-TRC20")
            amount_crypto = await calculate_usdt_amount_with_tax(
                int(settings.arz_usd or 0), amount, reserved_amounts=reserved
            )
        elif currency == "usdt-ton":
            wallet = await WalletCRUD().get_wallet_by_type("USDT-TON")
            amount_crypto = await calculate_usdt_amount_with_tax(
                int(settings.arz_usd or 0), amount, reserved_amounts=reserved
            )
        elif currency == "usdt-bep20":
            wallet = await WalletCRUD().get_wallet_by_type("USDT-BEP20")
            amount_crypto = await calculate_usdt_amount_with_tax(
                int(settings.arz_usd or 0), amount, reserved_amounts=reserved
            )
        elif currency == "pol":
            wallet = await WalletCRUD().get_wallet_by_type("POL")
            amount_crypto = await calculate_pol_amount_with_tax(
                int(settings.arz_pol or 0), amount, reserved_amounts=reserved
            )
        else:
            wallet = await WalletCRUD().get_wallet_by_type("TON")
            amount_crypto = await calculate_ton_amount_with_tax(
                int(settings.arz_ton or 0), amount, reserved_amounts=reserved
            )
        if not wallet:
            return BalanceDepositCryptoResponse(
                ok=False,
                error=f"کیف پول {currency.upper()} در سیستم ثبت نشده است.",
            )
        await add_order_crypto_payment(
            order_id=order_id,
            user_id=user_id,
            arz=currency,
            amount=str(amount_crypto),
            amount_irt=amount,
            createtime=Time_Date()["stamp"],
            msg_id=None,
        )

        await enqueue(
            message=(
                f"#فاکتور_جدید_{currency.upper()} (وب‌اپ)\n"
                f"👤 شناسه کاربر: `{user_id}`\n"
                f"💡 شماره فاکتور: `{order_id}`\n"
                f"💵 مبلغ فاکتور: `{amount:,}` تومان\n"
                f"💰 مقدار {currency.upper()}: `{amount_crypto}`"
            ),
            log_type=LogType.CRYPTO,
        )

        return BalanceDepositCryptoResponse(
            ok=True,
            order_id=order_id,
            wallet_address=getattr(wallet, "address", None),
            amount_crypto=str(amount_crypto),
            amount_irt=amount,
            currency=currency.upper(),
        )
    except ValueError as e:
        return BalanceDepositCryptoResponse(ok=False, error=str(e))
    except Exception as e:
        return BalanceDepositCryptoResponse(ok=False, error=str(e))


@router.post("/webapp/balance/deposit/stars", response_model=BalanceDepositStarsResponse)
async def deposit_stars(request: BalanceDepositStarsRequest) -> BalanceDepositStarsResponse:
    """Create a Telegram Stars invoice link for Mini App openInvoice payment."""
    try:
        user_id = await authenticate_user(
            init_data=request.init_data,
            session_token=request.session_token,
        )
        settings = await SettingsManager().get_settings()
        if not settings or not getattr(settings, "cart_sta", False):
            return BalanceDepositStarsResponse(ok=False, error="پرداخت با استارز غیرفعال است")

        amount = request.amount
        min_a = int(settings.crypto_deposit_min or 0)
        max_a = int(settings.crypto_deposit_max or 0)
        if amount < min_a or amount > max_a:
            return BalanceDepositStarsResponse(
                ok=False,
                error=f"مبلغ باید بین {min_a:,} تا {max_a:,} تومان باشد",
            )
        if not int(getattr(settings, "arz_usd", 0) or 0):
            return BalanceDepositStarsResponse(ok=False, error="نرخ دلار برای محاسبه استارز تنظیم نشده است")

        tx, invoice_url, stars = await create_star_invoice_link(user_id, amount)
        usd_rate_irt = int(settings.arz_usd)
        return BalanceDepositStarsResponse(
            ok=True,
            message="فاکتور استارز آماده است. پرداخت را در تلگرام تکمیل کنید.",
            tx_id=int(tx.id),
            invoice_no=tx.invoice_no,
            amount_irt=amount,
            stars=stars,
            usd_rate_irt=usd_rate_irt,
            star_price_irt=round(usd_rate_irt * STAR_USD_PRICE, 2),
            invoice_url=invoice_url,
        )
    except ValueError as e:
        return BalanceDepositStarsResponse(ok=False, error=str(e))
    except Exception as e:
        logger.exception("Stars deposit failed")
        return BalanceDepositStarsResponse(ok=False, error=str(e))
