def chain_tx_id(tx: dict) -> str | None:
    for key in ("hash", "transactionHash", "txID", "txid", "id"):
        val = tx.get(key)
        if val:
            return str(val)
    nested = tx.get("transaction_id")
    if isinstance(nested, dict) and nested.get("hash"):
        return str(nested["hash"])
    return None
