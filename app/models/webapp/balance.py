"""WebApp DTOs: balance top-up methods and deposit flows (manual card, crypto)."""

from pydantic import BaseModel, Field


class BalanceMethodsRequest(BaseModel):
    """Auth for balance methods."""

    session_token: str | None = None
    init_data: str | None = None


class IrGatewayMethod(BaseModel):
    """An Iranian direct gateway this user may pay with."""

    key: str
    title: str
    sandbox: bool = False
    deposit_min: int = 0
    deposit_max: int = 0
    bonus_percent: int = 0


class BalanceMethodsResponse(BaseModel):
    """Balance top-up methods (same as bot)."""

    ok: bool
    pay_mode: bool = False
    arz_mode: bool = False
    cart_sta: bool = False
    manual_deposit_min: int = 0
    manual_deposit_max: int = 0
    crypto_deposit_min: int = 0
    crypto_deposit_max: int = 0
    card_number: str | None = None
    card_name: str | None = None
    manual_bonus_percent: int = 0
    crypto_bonus_percent: int = 0
    stars_bonus_percent: int = 0
    arz_usd: int = 0
    arz_trx: int = 0
    arz_ton: int = 0
    arz_pol: int = 0
    phone_verify_required: bool = False
    tonpays_enabled: bool = False
    tonpays_mode: str = "standard"
    tonpays_deposit_min: int = 0
    tonpays_deposit_max: int = 0
    tonpays_bonus_percent: int = 0
    ir_gateways: list[IrGatewayMethod] = Field(default_factory=list)
    error: str | None = None


class BalancePhoneRequestRequest(BaseModel):
    """Auth for arming Telegram contact-share phone verification."""

    session_token: str | None = None
    init_data: str | None = None


class BalancePhoneRequestResponse(BaseModel):
    ok: bool
    error: str | None = None


class BalanceDepositManualRequest(BaseModel):
    """Manual card deposit: amount in toman."""

    amount: int = Field(..., ge=1)
    session_token: str | None = None
    init_data: str | None = None


class BalanceDepositManualResponse(BaseModel):
    ok: bool
    message: str | None = None
    card_number: str | None = None
    card_name: str | None = None
    error: str | None = None


class BalanceDepositManualReceiptResponse(BaseModel):
    ok: bool
    message: str | None = None
    error: str | None = None


class BalanceDepositCryptoRequest(BaseModel):
    """Crypto deposit: amount in toman, currency trx/usdt/usdt-ton/usdt-bep20/ton/pol."""

    amount: int = Field(..., ge=1)
    currency: str = Field(..., description="trx, usdt, usdt-ton, usdt-bep20, ton or pol")
    session_token: str | None = None
    init_data: str | None = None


class BalanceDepositCryptoResponse(BaseModel):
    ok: bool
    order_id: int | None = None
    wallet_address: str | None = None
    amount_crypto: str | None = None
    amount_irt: int | None = None
    currency: str | None = None
    error: str | None = None


class BalanceDepositStarsRequest(BaseModel):
    """Stars deposit: amount in toman."""

    amount: int = Field(..., ge=1)
    session_token: str | None = None
    init_data: str | None = None


class BalanceDepositStarsResponse(BaseModel):
    ok: bool
    message: str | None = None
    tx_id: int | None = None
    invoice_no: str | None = None
    amount_irt: int | None = None
    stars: int | None = None
    usd_rate_irt: int | None = None
    star_price_irt: float | None = None
    invoice_url: str | None = None
    error: str | None = None


class BalanceTonPaysDepositRequest(BaseModel):
    """TonPays deposit: amount in toman."""

    amount: int = Field(..., ge=1)
    session_token: str | None = None
    init_data: str | None = None


class BalanceTonPaysInvoiceRequest(BaseModel):
    """Act on one of the caller's TonPays invoices by its local id."""

    invoice: int = Field(..., ge=1)
    session_token: str | None = None
    init_data: str | None = None


class BalanceTonPaysOpenRequest(BaseModel):
    session_token: str | None = None
    init_data: str | None = None


class TonPaysInvoiceView(BaseModel):
    id: int
    invoice_id: str | None = None
    mode: str
    amount: int
    final_amount: int | None = None
    status: str
    status_label: str
    invoice_url: str | None = None
    web_invoice_url: str | None = None
    card_number: str | None = None
    card_name: str | None = None
    receipt_sent: bool = False


class BalanceTonPaysInvoiceResponse(BaseModel):
    ok: bool
    message: str | None = None
    invoice: TonPaysInvoiceView | None = None
    error: str | None = None


class BalanceIrGatewayDepositRequest(BaseModel):
    """Iranian gateway deposit: amount in toman."""

    gateway: str = Field(..., min_length=1, max_length=20)
    amount: int = Field(..., ge=1)
    session_token: str | None = None
    init_data: str | None = None


class BalanceIrGatewayOpenRequest(BaseModel):
    """The caller's newest pending payment for one gateway."""

    gateway: str = Field(..., min_length=1, max_length=20)
    session_token: str | None = None
    init_data: str | None = None


class BalanceIrGatewayPaymentRequest(BaseModel):
    """Act on one of the caller's gateway payments by its local id."""

    payment: int = Field(..., ge=1)
    session_token: str | None = None
    init_data: str | None = None


class IrGatewayPaymentView(BaseModel):
    id: int
    gateway: str
    gateway_title: str
    order_id: str
    amount: int
    status: str
    status_label: str
    sandbox: bool = False
    payment_url: str | None = None
    ref_id: str | None = None


class BalanceIrGatewayPaymentResponse(BaseModel):
    ok: bool
    message: str | None = None
    payment: IrGatewayPaymentView | None = None
    error: str | None = None
