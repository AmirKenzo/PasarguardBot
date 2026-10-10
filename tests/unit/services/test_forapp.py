"""ForApp core: rial->toman normalization, candidates, unique-offset reserve."""

from __future__ import annotations

from app.services.payments.forapp import (
    coerce_raw_amount,
    forapp_candidates,
    is_valid_forapp_key,
    normalize_to_toman,
    reserve_payable_amount,
)
from app.services.payments.forapp_match import extract_deposit_fields


def test_normalize_rial_to_toman():
    assert normalize_to_toman(12_000_210, "rial") == 1_200_021
    assert normalize_to_toman(12_000_210, "") == 1_200_021
    assert normalize_to_toman(1_200_021, "toman") == 1_200_021
    assert normalize_to_toman(0, "rial") is None
    assert normalize_to_toman(-5, "rial") is None


def test_candidates_include_divided_fallback():
    cands = forapp_candidates(12_000_210, "rial")
    assert cands[0] == 1_200_021
    assert 12_000_210 in cands  # raw fallback when unit is misdetected


def test_reserve_avoids_collisions_and_falls_back_linear():
    payable, offset = reserve_payable_amount(1_200_000, {1_200_001, 1_200_002}, random_fn=lambda: 0.0)
    # random_fn 0.0 -> offset 1 collides, linear scan finds next free slot
    assert (payable, offset) == (1_200_003, 3)


def test_reserve_returns_none_when_exhausted():
    taken = set(range(100_001, 101_000))
    assert reserve_payable_amount(100_000, taken, random_fn=lambda: 0.5) is None


def test_key_validation():
    assert is_valid_forapp_key("abc", ["abc"])
    assert not is_valid_forapp_key("abc", ["abd"])
    assert not is_valid_forapp_key("", ["abc"])
    assert not is_valid_forapp_key("abc", [])


def test_coerce_raw_amount():
    assert coerce_raw_amount("12,000,210") == 12_000_210
    assert coerce_raw_amount(5) == 5
    assert coerce_raw_amount("nope") is None
    assert coerce_raw_amount(True) is None


def test_extract_deposit_fields_lenient():
    fields = extract_deposit_fields(
        {"data": {"amount": "12000210", "unit": "rial", "sender": "Bank Melli", "body": "deposit"}}
    )
    assert fields["raw"] == 12_000_210
    assert fields["amount_toman"] == 1_200_021
    assert fields["is_deposit"] is True
    assert fields["deposit_id"]


def test_extract_real_forapp_default_payload():
    """Exact shape of ForApp's default JSON template (Request.defaultBody)."""
    fields = extract_deposit_fields(
        {
            "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
            "test": False,
            "sender": "98500012",
            "bank": "ملت",
            "body": "بانک ملت\nواریز:1,200,021\nمانده:15,200,000",
            "amount": 12_000_210,
            "code": "210",
            "unit": "rial",
            "is_deposit": True,
            "received_at": "2026-10-10T12:00:00+03:30",
            "received_at_ms": 1791234567890,
            "attempt": 1,
            "device": "samsung SM-A546B",
        },
        fallback_id="ignored-when-body-id-present",
    )
    assert fields["deposit_id"] == "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    assert fields["raw"] == 12_000_210
    assert fields["amount_toman"] == 1_200_021
    assert fields["code"] == "210"
    assert fields["received_at_ms"] == 1791234567890
    assert fields["is_test"] is False


def test_extract_forapp_test_button_payload():
    fields = extract_deposit_fields(
        {
            "id": "test-3fa85f64-5717-4562-b3fc-2c963f66afa6",
            "test": True,
            "sender": "ForApp",
            "bank": "آزمایشی",
            "body": "پیامک آزمایشی ForApp\nواریز: 1,000,123 ریال",
            "amount": 1_000_123,
            "code": "123",
            "unit": "rial",
            "is_deposit": True,
            "received_at_ms": 1791234567890,
            "attempt": 1,
            "device": "samsung SM-A546B",
        }
    )
    assert fields["is_test"] is True
    assert fields["amount_toman"] == 100_012  # 1,000,123 rial -> toman


def test_extract_idempotency_key_fallback():
    fields = extract_deposit_fields({"amount": 1000, "unit": "rial"}, fallback_id="hdr-key-1")
    assert fields["deposit_id"] == "hdr-key-1"


def test_extract_null_is_deposit_treated_as_candidate():
    fields = extract_deposit_fields({"id": "x", "amount": 1000, "unit": "rial", "is_deposit": None})
    assert fields["is_deposit"] is True


def test_bank_deposit_upsert_compiles_on_all_dialects():
    """The idempotent ledger upsert must build valid SQL for MySQL/PG/SQLite.

    Regression test: the MySQL branch once used Postgres-only `.excluded`,
    which only blew up against a real MySQL server (unit tests run sqlite).
    """
    from sqlalchemy.dialects import mysql, postgresql, sqlite

    from app.db.crud import bank_deposits as crud

    values = {
        "id": "sms-1",
        "raw_amount": 2_000_210,
        "amount_toman": 200_021,
        "unit": "rial",
        "sender": "98500012",
        "bank": "ملت",
        "body": "probe",
        "is_deposit": True,
        "received_at_ms": 1791234567890,
        "device": "dev",
        "attempt": 1,
        "is_test": False,
        "created_at": 1791234567,
    }
    cases = [
        ("mysql", mysql.dialect(), "ON DUPLICATE KEY UPDATE"),
        ("postgresql", postgresql.dialect(), "ON CONFLICT"),
        ("sqlite", sqlite.dialect(), "ON CONFLICT"),
    ]
    original = crud.DATABASE_DIALECT
    try:
        for forced, dialect, marker in cases:
            crud.DATABASE_DIALECT = forced
            compiled = str(crud.build_bank_deposit_upsert(values).compile(dialect=dialect))
            assert "bank_deposits" in compiled
            assert marker in compiled
    finally:
        crud.DATABASE_DIALECT = original
