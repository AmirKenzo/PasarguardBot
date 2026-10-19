"""Declarative bank SMS deposit rules for auto-card confirmation.

Sources adapted from Faoxima card.php and Mana Iranian bank parser tests.
Amounts are captured as shown in SMS (usually RIAL). TOMAN rules convert ×10 in the parser.
"""

from __future__ import annotations

from app.models.sms_auto_card import AmountUnit, BankSmsRule

# Priority: 10-49 specific phrases, 50-99 typical formats, 100+ fallbacks.

BANK_SMS_RULES: tuple[BankSmsRule, ...] = (
    BankSmsRule(
        bank_id="blu",
        name="Blu Bank",
        pattern=r"(\d[\d,]*)\s*ریال\s*به\s*حساب\s*شما\s*نشست",
        unit=AmountUnit.RIAL,
        priority=10,
        require_any=("واریز", "بلو"),
        reject_any=("برداشت", "خرید"),
    ),
    BankSmsRule(
        bank_id="gardeshgari",
        name="Bank Gardeshgari",
        pattern=r"مبلغ:\s*([\d,]+)\s*ریال",
        unit=AmountUnit.RIAL,
        priority=20,
    ),
    BankSmsRule(
        bank_id="gardeshgari",
        name="Bank Gardeshgari",
        pattern=r"مبلغ:\s*([\d,]+)",
        unit=AmountUnit.RIAL,
        priority=25,
        require_any=("مبلغ",),
        reject_any=("برداشت", "خرید", "رمز"),
    ),
    BankSmsRule(
        bank_id="saman",
        name="Bank Saman / Sepah",
        pattern=r"مبلغ:\s*([\d,]+)\s*ریال",
        unit=AmountUnit.RIAL,
        priority=20,
    ),
    BankSmsRule(
        bank_id="melli",
        name="Bank Melli",
        pattern=r"انتقال:\s*([\d,]+)\s*\+",
        unit=AmountUnit.RIAL,
        priority=30,
    ),
    BankSmsRule(
        bank_id="saderat",
        name="Bank Saderat",
        pattern=r"انتقال:\s*([\d,]+)",
        unit=AmountUnit.RIAL,
        priority=35,
        require_any=("انتقال",),
        reject_any=("برداشت", "خرید"),
    ),
    BankSmsRule(
        bank_id="mellat",
        name="Bank Mellat",
        pattern=r"واریز\s*([\d,]+)",
        unit=AmountUnit.RIAL,
        priority=30,
        reject_any=("برداشت", "خرید"),
    ),
    BankSmsRule(
        bank_id="tejarat",
        name="Bank Tejarat",
        pattern=r"واریز\s*:\s*([\d,]+)",
        unit=AmountUnit.RIAL,
        priority=30,
        reject_any=("برداشت", "خرید"),
    ),
    BankSmsRule(
        bank_id="keshavarzi",
        name="Bank Keshavarzi",
        pattern=r"واریز\s*([\d,]+)",
        unit=AmountUnit.RIAL,
        priority=30,
        reject_any=("برداشت", "خرید"),
    ),
    BankSmsRule(
        bank_id="resalat",
        name="Bank Resalat",
        pattern=r"\+([\d,]+)",
        unit=AmountUnit.RIAL,
        priority=40,
        reject_any=("برداشت", "خرید", "رمز"),
    ),
    BankSmsRule(
        bank_id="shahr",
        name="Bank Shahr",
        pattern=r"مبلغ:\s*([\d,]+)\s*ریال",
        unit=AmountUnit.RIAL,
        priority=20,
    ),
    BankSmsRule(
        bank_id="maskan",
        name="Bank Maskan",
        pattern=r"انتقال\s*اینترنت:\D*([\d,]+)",
        unit=AmountUnit.RIAL,
        priority=30,
        reject_any=("برداشت",),
    ),
    BankSmsRule(
        bank_id="parsian",
        name="Bank Parsian",
        pattern=r"مبلغ:\s*([\d,]+)\s*\+",
        unit=AmountUnit.RIAL,
        priority=30,
    ),
    BankSmsRule(
        bank_id="pasargad",
        name="Bank Pasargad / Vipad",
        pattern=r"\+([\d,]+)",
        unit=AmountUnit.RIAL,
        priority=45,
        reject_any=("برداشت", "خرید", "رمز"),
    ),
    BankSmsRule(
        bank_id="refah",
        name="Bank Refah",
        pattern=r"(?:کارت|واریز)\s*([\d,]+)\s*\+",
        unit=AmountUnit.RIAL,
        priority=30,
        reject_any=("برداشت", "خرید"),
    ),
    BankSmsRule(
        bank_id="refah",
        name="Bank Refah",
        pattern=r"([\d,]+)\+",
        unit=AmountUnit.RIAL,
        priority=50,
        require_any=("رفاه", "کارت"),
        reject_any=("برداشت", "خرید"),
    ),
    BankSmsRule(
        bank_id="gharz",
        name="Gharzolhasaneh",
        pattern=r"([\d,]+)\+",
        unit=AmountUnit.RIAL,
        priority=55,
        reject_any=("برداشت", "خرید"),
    ),
)


def sorted_bank_rules() -> tuple[BankSmsRule, ...]:
    """Return rules sorted by priority then bank_id for stable matching."""
    return tuple(sorted(BANK_SMS_RULES, key=lambda rule: (rule.priority, rule.bank_id)))
