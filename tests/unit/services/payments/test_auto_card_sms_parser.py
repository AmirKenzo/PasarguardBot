"""Unit tests for multi-bank SMS deposit parsing."""

from __future__ import annotations

from app.services.payments.auto_card_sms_parser import build_sms_envelope, extract_deposit_rial


def test_blu_deposit_with_forwarder_footer() -> None:
    text = (
        "بلو\n"
        "واریز پول\n"
        "امیرحسین عزیز، 112,000,000 ریال به حساب شما نشست.\n"
        "موجودی: 981,610,409 ریال\n"
        "۳:۳۳\n"
        "۱۴۰۵.۰۵.۱۷\n"
        "SIM1_\n"
        "SubId：0\n"
        "2026-08-09 00:00:23\n"
        "samsung SM-S908E"
    )
    parsed = extract_deposit_rial(text)
    assert parsed is not None
    assert parsed.bank_id == "blu"
    assert parsed.amount_rial == 112_000_000


def test_resalat_style_plus_amount() -> None:
    text = (
        "777.888.25544558.1\n"
        "+1,000,000,000\n"
        "12/02_04:33\n"
        "مانده: 2,473,697,408\n"
        "SIM1_\n"
        "SubId：0\n"
        "2026-08-08 23:59:37\n"
        "samsung SM-S908E"
    )
    parsed = extract_deposit_rial(text)
    assert parsed is not None
    assert parsed.amount_rial == 1_000_000_000


def test_gardeshgari_mablagh_rial() -> None:
    text = "مبلغ: 1,000,586 ريال واريز شد"
    parsed = extract_deposit_rial(text)
    assert parsed is not None
    assert parsed.amount_rial == 1_000_586


def test_mellat_variz() -> None:
    text = "واریز1,250,000 مانده5,000,000"
    parsed = extract_deposit_rial(text)
    assert parsed is not None
    assert parsed.amount_rial == 1_250_000


def test_keshavarzi_deposit() -> None:
    text = "واريز4,000,000\nمانده8,915,929\n040825-11:32\nکارت8783*"
    parsed = extract_deposit_rial(text)
    assert parsed is not None
    assert parsed.amount_rial == 4_000_000


def test_refah_card_plus() -> None:
    text = "بانک رفاه\nحساب207853186\nکارت5,000,000+\nمانده81,108,644"
    parsed = extract_deposit_rial(text)
    assert parsed is not None
    assert parsed.amount_rial == 5_000_000


def test_withdrawal_ignored() -> None:
    text = "برداشت24,000\nمانده6,917,559"
    assert extract_deposit_rial(text) is None


def test_legacy_json_envelope() -> None:
    envelope = build_sms_envelope(json_body={"text": "hello", "key": "ak"})
    assert envelope is not None
    assert envelope.text == "hello"
    assert envelope.key == "ak"


def test_tobank_form_envelope() -> None:
    envelope = build_sms_envelope(
        form_body={
            "from": "",
            "content": "بلو\nواریز پول\n112,000,000 ریال به حساب شما نشست.",
            "timestamp": "1786221023133",
        }
    )
    assert envelope is not None
    assert "واریز" in envelope.text
    assert envelope.timestamp == "1786221023133"
