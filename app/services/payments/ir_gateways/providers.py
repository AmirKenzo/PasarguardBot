"""Gateway providers: the only per-gateway code. Adding a gateway = one subclass registered in GATEWAYS.

Each provider knows its API (request/verify), its callback query string and what a valid merchant looks
like. Everything else (DB rows, crediting, bot/web/panel UI, polling) is shared and keyed by `key`.
This module has no Telegram/DB imports so keyboards and settings helpers can use it.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, ClassVar, Literal

import httpx

from app.logger import get_logger

logger = get_logger(__name__)

Outcome = Literal["paid", "unpaid", "failed"]


class GatewayError(Exception):
    """A gateway API or flow error with a user-facing Persian message."""

    def __init__(self, message: str, code: int | None = None):
        super().__init__(message)
        self.message = message
        self.code = code


@dataclass(frozen=True)
class VerifyResult:
    """paid: credit it; unpaid: not paid (yet); failed: can never succeed, close it."""

    outcome: Outcome
    ref_id: str | None = None
    card_pan: str | None = None
    detail: str | None = None


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except TypeError, ValueError:
        return None


class IrGatewayProvider(ABC):
    key: ClassVar[str]
    title: ClassVar[str]
    emoji: ClassVar[str]
    order_prefix: ClassVar[str]
    merchant_pattern: ClassVar[re.Pattern[str]]
    merchant_hint: ClassVar[str]
    sandbox_hint: ClassVar[str]
    timeout: ClassVar[float] = 20.0

    def __init__(self) -> None:
        # Replaced by tests with an httpx.MockTransport.
        self.transport: httpx.AsyncBaseTransport | None = None

    def is_valid_merchant(self, value: str) -> bool:
        return bool(self.merchant_pattern.match((value or "").strip()))

    @abstractmethod
    def merchant_for(self, stored: str, sandbox: bool) -> str:
        """Merchant to send to the API; test mode may substitute a public test merchant."""

    @abstractmethod
    def start_pay_url(self, authority: str, sandbox: bool) -> str: ...

    @abstractmethod
    def parse_callback(self, query: Mapping[str, str]) -> tuple[str, bool]:
        """(authority, buyer_canceled) from the buyer's return URL. Never trusted for crediting."""

    @abstractmethod
    async def request_payment(
        self, *, merchant: str, sandbox: bool, amount_rial: int, description: str, callback: str, order_id: str
    ) -> str:
        """Open a payment and return its authority (the id the buyer pays and we verify with)."""

    @abstractmethod
    async def verify(
        self, *, merchant: str, sandbox: bool, authority: str, amount_rial: int, order_id: str
    ) -> VerifyResult: ...

    async def _post(self, base_url: str, path: str, body: dict[str, Any]) -> tuple[httpx.Response, Any]:
        if not body.get("merchant") and not body.get("merchant_id"):
            raise GatewayError(f"مرچنت {self.title} تنظیم نشده است.")
        try:
            async with httpx.AsyncClient(base_url=base_url, timeout=self.timeout, transport=self.transport) as client:
                response = await client.post(path, json=body, headers={"Accept": "application/json"})
        except httpx.HTTPError as e:
            logger.error("%s request %s failed: %s", self.key, path, e)
            raise GatewayError(f"ارتباط با {self.title} برقرار نشد. کمی بعد دوباره تلاش کنید.") from e
        try:
            return response, response.json()
        except ValueError:
            return response, None


# ---------------------------------------------------------------------------
# Zarinpal (API v4)
# ---------------------------------------------------------------------------


class ZarinpalProvider(IrGatewayProvider):
    key = "zarinpal"
    title = "زرین‌پال"
    emoji = "🟡"
    order_prefix = "ZP"
    merchant_pattern = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
    merchant_hint = "مرچنت کد ۳۶ کاراکتری (UUID) از پنل زرین‌پال"
    sandbox_hint = "sandbox.zarinpal.com؛ بدون نیاز به مرچنت کد"

    LIVE_BASE_URL = "https://payment.zarinpal.com"
    SANDBOX_BASE_URL = "https://sandbox.zarinpal.com"
    # The sandbox accepts any UUID-shaped merchant id.
    SANDBOX_MERCHANT = "00000000-0000-0000-0000-000000000000"
    PAID_CODES: ClassVar[tuple[int, ...]] = (100, 101)
    FAILED_CODES: ClassVar[tuple[int, ...]] = (
        -50,
        -53,
        -54,
    )  # amount mismatch, foreign or invalid authority: never succeeds later
    ERRORS: ClassVar[dict[int, str]] = {
        -9: "اطلاعات ارسالی به زرین‌پال نامعتبر است (مرچنت، مبلغ یا آدرس بازگشت).",
        -10: "مرچنت کد یا IP سرور در زرین‌پال معتبر نیست.",
        -11: "مرچنت کد زرین‌پال فعال نیست.",
        -12: "تلاش بیش از حد مجاز؛ کمی بعد دوباره تلاش کنید.",
        -15: "درگاه زرین‌پال تعلیق شده است.",
        -16: "سطح تأیید پذیرنده در زرین‌پال کافی نیست.",
    }

    def merchant_for(self, stored: str, sandbox: bool) -> str:
        if sandbox:
            return stored if self.is_valid_merchant(stored) else self.SANDBOX_MERCHANT
        return stored

    def _base(self, sandbox: bool) -> str:
        return self.SANDBOX_BASE_URL if sandbox else self.LIVE_BASE_URL

    def start_pay_url(self, authority: str, sandbox: bool) -> str:
        return f"{self._base(sandbox)}/pg/StartPay/{authority}"

    def parse_callback(self, query: Mapping[str, str]) -> tuple[str, bool]:
        return str(query.get("Authority") or "").strip(), str(query.get("Status") or "").upper() != "OK"

    async def _call(self, sandbox: bool, path: str, body: dict[str, Any]) -> tuple[int | None, dict[str, Any]]:
        response, raw = await self._post(self._base(sandbox), path, body)
        if not isinstance(raw, dict):
            raise GatewayError(f"پاسخ نامعتبر از زرین‌پال (HTTP {response.status_code}).")
        payload = raw.get("data") if isinstance(raw.get("data"), dict) else {}
        errors = raw.get("errors")
        if isinstance(errors, dict) and errors.get("code") is not None:
            logger.warning("zarinpal %s -> %s: %s", path, errors.get("code"), errors.get("message"))
            return _as_int(errors.get("code")), payload
        code = _as_int(payload.get("code"))
        if code is None:
            raise GatewayError(f"پاسخ نامعتبر از زرین‌پال (HTTP {response.status_code}).")
        return code, payload

    async def request_payment(
        self, *, merchant: str, sandbox: bool, amount_rial: int, description: str, callback: str, order_id: str
    ) -> str:
        code, data = await self._call(
            sandbox,
            "/pg/v4/payment/request.json",
            {
                "merchant_id": merchant,
                "amount": int(amount_rial),
                "currency": "IRR",
                "description": description,
                "callback_url": callback,
                "metadata": {"order_id": order_id},
            },
        )
        authority = str(data.get("authority") or "")
        if code != 100 or not authority:
            raise GatewayError(self.ERRORS.get(code or 0, f"خطای زرین‌پال (کد {code})."), code)
        return authority

    async def verify(
        self, *, merchant: str, sandbox: bool, authority: str, amount_rial: int, order_id: str
    ) -> VerifyResult:
        code, data = await self._call(
            sandbox,
            "/pg/v4/payment/verify.json",
            {"merchant_id": merchant, "amount": int(amount_rial), "authority": authority},
        )
        if code in self.PAID_CODES:
            ref_id = data.get("ref_id")
            return VerifyResult("paid", str(ref_id) if ref_id is not None else None, data.get("card_pan") or None)
        if code in self.FAILED_CODES:
            return VerifyResult("failed", detail=f"code {code}")
        return VerifyResult("unpaid", detail=f"code {code}")


# ---------------------------------------------------------------------------
# Zibal (API v1)
# ---------------------------------------------------------------------------


class ZibalProvider(IrGatewayProvider):
    key = "zibal"
    title = "زیبال"
    emoji = "🔵"
    order_prefix = "ZB"
    merchant_pattern = re.compile(r"^[A-Za-z0-9_-]{4,64}$")
    merchant_hint = "مرچنت درگاه از پنل زیبال (حروف انگلیسی، عدد، - و _)"
    sandbox_hint = "مرچنت آزمایشی zibal؛ بدون نیاز به حساب"

    BASE_URL = "https://gateway.zibal.ir"
    SANDBOX_MERCHANT = "zibal"
    ALREADY_VERIFIED = 201
    INVALID_TRACK = 203
    ERRORS: ClassVar[dict[int, str]] = {
        102: "مرچنت زیبال پیدا نشد.",
        103: "مرچنت زیبال غیرفعال است.",
        104: "مرچنت زیبال نامعتبر است.",
        105: "مبلغ باید بیشتر از ۱۰۰ تومان باشد.",
        106: "آدرس بازگشت (callbackUrl) نامعتبر است.",
        113: "مبلغ بیشتر از سقف مجاز تراکنش در زیبال است.",
    }

    def is_valid_merchant(self, value: str) -> bool:
        return super().is_valid_merchant(value) and value.strip() != self.SANDBOX_MERCHANT

    def merchant_for(self, stored: str, sandbox: bool) -> str:
        return self.SANDBOX_MERCHANT if sandbox else stored

    def start_pay_url(self, authority: str, sandbox: bool) -> str:
        return f"{self.BASE_URL}/start/{authority}"

    def parse_callback(self, query: Mapping[str, str]) -> tuple[str, bool]:
        return str(query.get("trackId") or "").strip(), str(query.get("success") or "").strip() != "1"

    async def _call(self, path: str, body: dict[str, Any]) -> tuple[int | None, dict[str, Any]]:
        response, raw = await self._post(self.BASE_URL, path, body)
        code = _as_int(raw.get("result")) if isinstance(raw, dict) else None
        if code is None:
            raise GatewayError(f"پاسخ نامعتبر از زیبال (HTTP {response.status_code}).")
        if code not in (100, self.ALREADY_VERIFIED):
            logger.warning("zibal %s -> %s: %s", path, code, raw.get("message"))
        return code, raw

    async def request_payment(
        self, *, merchant: str, sandbox: bool, amount_rial: int, description: str, callback: str, order_id: str
    ) -> str:
        code, data = await self._call(
            "/v1/request",
            {
                "merchant": merchant,
                "amount": int(amount_rial),
                "callbackUrl": callback,
                "description": description,
                "orderId": order_id,
            },
        )
        track_id = str(data.get("trackId") or "")
        if code != 100 or not track_id:
            raise GatewayError(self.ERRORS.get(code or 0, f"خطای زیبال (کد {code})."), code)
        return track_id

    async def verify(
        self, *, merchant: str, sandbox: bool, authority: str, amount_rial: int, order_id: str
    ) -> VerifyResult:
        track_id = _as_int(authority) or authority
        code, data = await self._call("/v1/verify", {"merchant": merchant, "trackId": track_id})
        if code == self.ALREADY_VERIFIED and data.get("amount") is None:
            # A repeated verify may omit the details; inquiry returns them for the same trackId.
            inquiry_code, inquiry = await self._call("/v1/inquiry", {"merchant": merchant, "trackId": track_id})
            if inquiry_code == 100:
                data = {**inquiry, **{k: v for k, v in data.items() if v is not None}}
        if code == self.INVALID_TRACK:
            return VerifyResult("failed", detail="invalid trackId")
        if code not in (100, self.ALREADY_VERIFIED):
            return VerifyResult("unpaid", detail=f"result {code}")
        # Zibal's verify does not take the amount, so check what it reports against the local row.
        paid_amount = _as_int(data.get("amount"))
        if paid_amount is not None and paid_amount != int(amount_rial):
            return VerifyResult("failed", detail=f"amount {paid_amount} != {amount_rial}")
        reported_order = data.get("orderId")
        if reported_order and str(reported_order) != order_id:
            return VerifyResult("failed", detail=f"orderId {reported_order} != {order_id}")
        ref = data.get("refNumber")
        card = data.get("cardNumber")
        return VerifyResult(
            "paid",
            str(ref) if ref not in (None, "") else None,
            str(card) if card and card != "-" else None,
        )


# Display order everywhere (bot, web app, panel, stats).
GATEWAYS: dict[str, IrGatewayProvider] = {provider.key: provider for provider in (ZarinpalProvider(), ZibalProvider())}


def get_provider(key: str) -> IrGatewayProvider:
    try:
        return GATEWAYS[key]
    except KeyError:
        raise GatewayError("درگاه پرداخت نامعتبر است.") from None
