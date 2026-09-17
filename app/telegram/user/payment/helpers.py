import math

from telethon import functions, types

from app import Kenzo
from app.db.crud.settings import SettingsManager
from app.db.crud.stars_transactions import StarsTransactionCRUD
from app.db.models.stars_transaction import StarsTransaction
from app.telegram.keyboards.home import bhome_buttons

STAR_USD_PRICE = 0.015  # price of one star in USD (50 stars = 0.75 USD)


async def calculate_star_amount(usd_price: int, amount_in_toman: int) -> int:
    """Calculate the number of stars based on toman amount and USD price."""
    toman_per_star = usd_price * STAR_USD_PRICE
    stars = amount_in_toman / toman_per_star
    return max(1, math.ceil(stars))


async def _build_star_invoice(user_id: int, amount: int) -> tuple[StarsTransaction, types.InputMediaInvoice, int]:
    """Create Stars DB row + Telegram invoice media shared by chat and Mini App flows."""
    settings = await SettingsManager().get_settings()
    stars = await calculate_star_amount(int(settings.arz_usd), amount)

    tx = await StarsTransactionCRUD().create(user_id=user_id, amount=amount, stars=stars)

    invoice = types.Invoice(
        currency="XTR",
        prices=[types.LabeledPrice(label="پرداخت با استارز", amount=stars)],
        test=False,
        name_requested=False,
        phone_requested=False,
        email_requested=False,
        shipping_address_requested=False,
        flexible=False,
        phone_to_provider=False,
        email_to_provider=False,
    )

    payload = f"stars:{tx.id}"
    media = types.InputMediaInvoice(
        title="افزایش موجودی",
        description="برای شارژ حساب تعداد ستاره های زیر را پرداخت کنید.",
        invoice=invoice,
        payload=payload.encode("utf-8"),
        provider="",
        provider_data=types.DataJSON("{}"),
        start_param="stars-pay",
    )
    return tx, media, stars


async def send_star_invoice(user_id: int, amount: int) -> None:
    """Send a Telegram Stars invoice to the user (bot chat flow)."""
    tx, media, stars = await _build_star_invoice(user_id, amount)

    caption = (
        "🧾 <b>فاکتور استارز</b>\n"
        f"💡 شماره فاکتور: <code>{tx.invoice_no}</code>\n"
        f"💵 مبلغ: <code>{amount:,}</code> تومان ⭐ <code>{stars}</code> ستاره\n"
        "⏳ اعتبار: 30 دقیقه\n"
    )

    await Kenzo.send_message(user_id, message="⏳", parse_mode="html", buttons=await bhome_buttons(user_id, "fa"))
    message = await Kenzo.send_message(user_id, message=caption, file=media, parse_mode="html")
    await StarsTransactionCRUD().update(tx.id, message_id=message.id)


async def create_star_invoice_link(user_id: int, amount: int) -> tuple[StarsTransaction, str, int]:
    """Create a Stars invoice link usable with Telegram.WebApp.openInvoice."""
    tx, media, stars = await _build_star_invoice(user_id, amount)
    exported = await Kenzo(functions.payments.ExportInvoiceRequest(invoice_media=media))
    url = getattr(exported, "url", None) or ""
    if not url:
        raise ValueError("لینک فاکتور استارز ساخته نشد")
    return tx, url, stars
