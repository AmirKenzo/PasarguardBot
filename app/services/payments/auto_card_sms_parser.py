"""Auto-card multi-bank SMS deposit parser."""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any
from urllib.parse import urlparse

from pydantic import ValidationError

import config
from app.models.sms_auto_card import AmountUnit, BankSmsRule, ParsedDeposit, SmsWebhookEnvelope
from app.services.payments.auto_card_sms_rules import sorted_bank_rules

_PERSIAN_DIGIT_MAP = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_ARABIC_YEH_KEH = str.maketrans({"ي": "ی", "ك": "ک", "ة": "ه"})
_FORWARDER_FOOTER_RE = re.compile(
    r"(?:\r?\n)\s*SIM\d*_.*$",
    re.IGNORECASE | re.DOTALL,
)


def normalize_sms_text(text: str) -> str:
    """Normalize digits/letters and strip SMS-forwarder metadata footers."""
    cleaned = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    cleaned = cleaned.translate(_PERSIAN_DIGIT_MAP).translate(_ARABIC_YEH_KEH)
    cleaned = _FORWARDER_FOOTER_RE.sub("", cleaned)
    return cleaned.strip()


def parse_amount_digits(raw: str) -> int | None:
    """Parse a captured amount token into an int (commas/spaces removed)."""
    digits = re.sub(r"[^\d]", "", raw or "")
    if not digits:
        return None
    try:
        value = int(digits)
    except ValueError:
        return None
    return value if value > 0 else None


@lru_cache(maxsize=1)
def _compiled_rules() -> tuple[tuple[BankSmsRule, re.Pattern[str]], ...]:
    return tuple(
        (rule, re.compile(rule.pattern, re.IGNORECASE | re.UNICODE | re.MULTILINE)) for rule in sorted_bank_rules()
    )


def _rule_allowed(rule: BankSmsRule, text: str) -> bool:
    if rule.reject_any and any(token in text for token in rule.reject_any):
        return False
    if not rule.require_any:
        return True
    return any(token in text for token in rule.require_any)


def _to_rial(raw_amount: int, unit: AmountUnit) -> int:
    if unit is AmountUnit.TOMAN:
        return raw_amount * 10
    return raw_amount


def extract_deposit_rial(sms_text: str) -> ParsedDeposit | None:
    """Extract deposit amount in RIAL from a bank SMS body."""
    text = normalize_sms_text(sms_text)
    if not text:
        return None

    for rule, pattern in _compiled_rules():
        if not _rule_allowed(rule, text):
            continue
        match = pattern.search(text)
        if not match:
            continue
        raw_amount = parse_amount_digits(match.group(1))
        if raw_amount is None:
            continue
        amount_rial = _to_rial(raw_amount, rule.unit)
        if amount_rial <= 0:
            continue
        return ParsedDeposit(
            bank_id=rule.bank_id,
            bank_name=rule.name,
            amount_rial=amount_rial,
            raw_amount=raw_amount,
            unit=rule.unit,
        )
    return None


def build_sms_envelope(
    *,
    json_body: dict[str, Any] | None = None,
    form_body: dict[str, Any] | None = None,
) -> SmsWebhookEnvelope | None:
    """Build a normalized envelope from JSON and/or form fields."""
    data: dict[str, Any] = {}
    if form_body:
        data.update({str(k): v for k, v in form_body.items()})
    if json_body:
        data.update({str(k): v for k, v in json_body.items()})

    text = _first_str(data, ("text", "content", "msg", "message", "body"))
    if not text:
        return None

    try:
        return SmsWebhookEnvelope(
            text=text,
            sender=_first_str(data, ("from", "sender")),
            timestamp=_first_str(data, ("timestamp", "time", "ts")),
            key=_first_str(data, ("key", "secret", "api_key")),
            message_id=_first_str(data, ("id",)),
            is_test=_to_bool(data.get("test")) is True,
            is_deposit=_to_bool(data.get("is_deposit")),
            amount_rial=_forwarded_amount_rial(data),
        )
    except ValidationError:
        return None


def _to_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("true", "1", "yes"):
            return True
        if lowered in ("false", "0", "no"):
            return False
    return None


def _forwarded_amount_rial(data: dict[str, Any]) -> int | None:
    raw = data.get("amount")
    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, float):
        raw = int(raw)
    amount = parse_amount_digits(str(raw))
    if amount is None:
        return None
    unit = str(data.get("unit") or AmountUnit.RIAL.value).strip().lower()
    if unit == AmountUnit.TOMAN.value:
        return _to_rial(amount, AmountUnit.TOMAN)
    if unit != AmountUnit.RIAL.value:
        return None
    return amount


def _first_str(data: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def clear_parser_cache() -> None:
    """Clear compiled regex cache (useful in tests after monkeypatching rules)."""
    _compiled_rules.cache_clear()


def sms_webhook_url() -> str | None:
    webapp = (config.WEBAPP_URL or "").strip().rstrip("/")
    parsed = urlparse(webapp)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    if webapp.endswith("/webapp"):
        return f"{webapp[: -len('/webapp')]}/sms"
    return f"{parsed.scheme}://{parsed.netloc}/api/sms"
