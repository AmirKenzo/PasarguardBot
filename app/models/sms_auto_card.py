"""Pydantic schemas for auto-card SMS webhook and bank deposit parsing."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class AmountUnit(StrEnum):
    """Unit encoded in the SMS amount capture group."""

    RIAL = "rial"
    TOMAN = "toman"


class BankSmsRule(BaseModel):
    """Declarative deposit-amount rule for one bank SMS format.

    Add/update banks in ``app.services.payments.auto_card_sms_rules``.
    """

    model_config = ConfigDict(frozen=True)

    bank_id: str = Field(..., description="Stable machine id, e.g. blu, mellat")
    name: str = Field(..., description="Human-readable bank name")
    pattern: str = Field(..., description="Regex with a single capturing group for the amount")
    unit: AmountUnit = AmountUnit.RIAL
    priority: int = Field(
        default=100,
        description="Lower runs first; put more specific patterns first",
    )
    require_any: tuple[str, ...] = Field(
        default=(),
        description="If set, normalized text must contain at least one of these substrings",
    )
    reject_any: tuple[str, ...] = Field(
        default=(),
        description="Skip rule when normalized text contains any of these substrings",
    )


class ParsedDeposit(BaseModel):
    """Successful deposit parse result (amount always in RIAL for auto-card matching)."""

    model_config = ConfigDict(frozen=True)

    bank_id: str
    bank_name: str
    amount_rial: int = Field(..., gt=0)
    raw_amount: int = Field(..., description="Numeric value as captured before unit conversion")
    unit: AmountUnit


class SmsWebhookEnvelope(BaseModel):
    """Normalized webhook payload from JSON or form-urlencoded forwarders."""

    model_config = ConfigDict(frozen=True)

    text: str
    sender: str | None = None
    timestamp: str | None = None
    key: str | None = None
    message_id: str | None = Field(default=None, description="Stable per-SMS id, used to drop repeated deliveries")
    is_test: bool = False
    is_deposit: bool | None = None
    amount_rial: int | None = Field(default=None, gt=0, description="Amount parsed on the phone, in RIAL")
