"""Transaction id extraction across the different chain explorer payload shapes."""

from __future__ import annotations

import pytest

from app.jobs.payments.tx_id import chain_tx_id


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"hash": "a"}, "a"),
        ({"transactionHash": "b"}, "b"),
        ({"txID": "c"}, "c"),
        ({"txid": "d"}, "d"),
        ({"id": "e"}, "e"),
        ({"transaction_id": {"hash": "ton-hash"}}, "ton-hash"),
    ],
    ids=["hash", "transactionHash", "txID", "txid", "id", "ton-nested-hash"],
)
def test_chain_tx_id_reads_each_known_key(payload: dict, expected: str):
    assert chain_tx_id(payload) == expected


def test_chain_tx_id_is_none_without_a_known_key():
    assert chain_tx_id({}) is None


@pytest.mark.parametrize("payload", [{"hash": "N/A"}, {"hash": "x" * 129}], ids=["placeholder", "too-long"])
def test_chain_tx_id_is_none_when_unusable(payload: dict):
    assert chain_tx_id(payload) is None
