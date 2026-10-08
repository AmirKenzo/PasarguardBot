"""Only successful native TRX transfers may pay a TRX invoice; TRC10 tokens must be rejected.

Samples mirror real TronScan responses (``/api/transaction`` and ``/api/transfer``).
"""

from __future__ import annotations

from app.jobs.payments.trx import is_native_trx_transfer

TRX_TOKEN_INFO = {"tokenId": "_", "tokenAbbr": "trx", "tokenName": "trx", "tokenDecimal": 6, "tokenType": "trc10"}
TRC10_TOKEN_INFO = {
    "tokenId": "1005141",
    "tokenAbbr": "Gas97com",
    "tokenName": "Gas97",
    "tokenDecimal": 6,
    "tokenType": "trc10",
}


def _transaction(contract_type: int, token_info: dict, contract_ret: str = "SUCCESS") -> dict:
    return {"contractType": contract_type, "amount": "970000", "contractRet": contract_ret, "tokenInfo": token_info}


def test_native_trx_transfer_is_accepted():
    assert is_native_trx_transfer(_transaction(1, TRX_TOKEN_INFO)) is True


def test_trc10_transfer_is_rejected():
    assert is_native_trx_transfer(_transaction(2, TRC10_TOKEN_INFO)) is False


def test_trc10_token_info_is_rejected_even_without_contract_type():
    # /api/transfer rows carry tokenInfo but no contractType.
    row = {"amount": 970000, "contractRet": "SUCCESS", "revert": False, "tokenInfo": TRC10_TOKEN_INFO}
    assert is_native_trx_transfer(row) is False


def test_transfer_endpoint_native_row_is_accepted():
    row = {"amount": 970000, "contractRet": "SUCCESS", "revert": False, "tokenInfo": TRX_TOKEN_INFO}
    assert is_native_trx_transfer(row) is True


def test_failed_transfer_is_rejected():
    assert is_native_trx_transfer(_transaction(1, TRX_TOKEN_INFO, contract_ret="REVERT")) is False


def test_reverted_transfer_is_rejected():
    row = {"amount": 970000, "revert": True, "tokenInfo": TRX_TOKEN_INFO}
    assert is_native_trx_transfer(row) is False


def test_row_without_any_token_marker_is_rejected():
    assert is_native_trx_transfer({"amount": "970000"}) is False


def test_transfer_contract_without_token_info_is_accepted():
    assert is_native_trx_transfer({"contractType": 1, "amount": "970000", "contractRet": "SUCCESS"}) is True
