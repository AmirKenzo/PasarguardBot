TX_HASH_MAX_LENGTH = 128
_PLACEHOLDERS = {"N/A"}


def _raw_tx_id(tx: dict) -> str | None:
    for key in ("hash", "transactionHash", "txID", "txid", "id"):
        val = tx.get(key)
        if val:
            return str(val)
    nested = tx.get("transaction_id")
    if isinstance(nested, dict):
        if nested.get("hash"):
            return str(nested["hash"])
    elif nested:
        return str(nested)
    return None


def chain_tx_id(tx: dict) -> str | None:
    """The transfer's on-chain id, or None when it has no usable one."""
    txid = _raw_tx_id(tx)
    if not txid or txid in _PLACEHOLDERS or len(txid) > TX_HASH_MAX_LENGTH:
        return None
    return txid
