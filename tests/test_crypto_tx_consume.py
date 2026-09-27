from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


chain_tx_id = _load("chain_tx_id_under_test", PROJECT_ROOT / "app/jobs/payments/tx_id.py").chain_tx_id


def test_chain_tx_id_key_fallbacks():
    assert chain_tx_id({"hash": "a"}) == "a"
    assert chain_tx_id({"transactionHash": "b"}) == "b"
    assert chain_tx_id({"txID": "c"}) == "c"
    assert chain_tx_id({"txid": "d"}) == "d"
    assert chain_tx_id({"id": "e"}) == "e"
    assert chain_tx_id({"transaction_id": {"hash": "ton-hash"}}) == "ton-hash"
    assert chain_tx_id({}) is None


def test_consumed_set_blocks_second_payment():
    payments = [{"id": 1, "amount": "1.0"}, {"id": 2, "amount": "1.0"}]
    txs = [{"hash": "same", "amount": "1.0"}]
    consumed: set[str] = set()
    matched = []
    for payment in payments:
        for tx in txs:
            txid = chain_tx_id(tx)
            if txid and txid in consumed:
                continue
            if tx["amount"] != payment["amount"]:
                continue
            matched.append(payment["id"])
            if txid:
                consumed.add(txid)
            break
    assert matched == [1]
