import hashlib
import hmac

from config import BOT_TOKEN

_SIGNATURE_LENGTH = 12
_PREFIX = "ref_"


def _compute_signature(payload: str) -> str:
    """Create a deterministic HMAC signature for the given payload."""
    digest = hmac.new(BOT_TOKEN.encode(), payload.encode(), hashlib.sha256)
    return digest.hexdigest()[:_SIGNATURE_LENGTH]


def build_referral_start_param(user_id: int) -> str:
    """Return a secure `start` parameter for the given user id."""
    payload = str(user_id)
    signature = _compute_signature(payload)
    return f"{_PREFIX}{payload}-{signature}"


def parse_referral_start_param(param: str) -> int | None:
    """
    Validate and decode a referral `start` parameter.

    Returns the referrer user id when valid, otherwise ``None``.
    """
    if not param:
        return None

    normalized = param.strip()
    if not normalized.startswith(_PREFIX):
        return None

    raw_payload = normalized[len(_PREFIX) :]
    try:
        user_part, signature = raw_payload.split("-", 1)
    except ValueError:
        return None

    if not user_part.isdigit():
        return None

    expected_signature = _compute_signature(user_part)
    if not hmac.compare_digest(expected_signature, signature.lower()):
        return None

    return int(user_part)
