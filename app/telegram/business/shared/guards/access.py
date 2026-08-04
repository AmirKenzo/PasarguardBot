"""Business connection registry and access control (multi-admin, JSON)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from telethon.tl import functions, types

import config
from app.logger import get_logger
from config import ADMIN_ID

logger = get_logger(__name__)

_PROJECT_ROOT = Path(config.__file__).resolve().parent
BUSINESS_CONNECTIONS_FILE = _PROJECT_ROOT / "business_connections.json"

KNOWN_BUSINESS_UPDATES = frozenset(
    {
        types.UpdateBotBusinessConnect,
        types.UpdateBotNewBusinessMessage,
        types.UpdateBotEditBusinessMessage,
        types.UpdateBotDeleteBusinessMessage,
        types.UpdateBusinessBotCallbackQuery,
    }
)


@dataclass(slots=True)
class BusinessConnectionRecord:
    user_id: int
    connection_id: str


def is_business_admin(user_id: int | None) -> bool:
    if user_id is None:
        return False
    return user_id in ADMIN_ID


def _parse_record(raw: object, user_id: int) -> BusinessConnectionRecord | None:
    if isinstance(raw, str):
        return BusinessConnectionRecord(user_id=user_id, connection_id=raw)
    if not isinstance(raw, dict):
        return None
    try:
        return BusinessConnectionRecord(
            user_id=int(raw.get("user_id", user_id)),
            connection_id=str(raw["connection_id"]),
        )
    except KeyError, TypeError, ValueError:
        return None


def _import_txt_if_needed() -> dict[int, BusinessConnectionRecord]:
    txt_path = _PROJECT_ROOT / "business_connections.txt"
    if not txt_path.is_file():
        return {}

    connections: dict[int, BusinessConnectionRecord] = {}
    with txt_path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or ":" not in line:
                continue
            user_part, connection_id = line.split(":", 1)
            try:
                user_id = int(user_part.strip())
            except ValueError:
                continue
            connections[user_id] = BusinessConnectionRecord(
                user_id=user_id,
                connection_id=connection_id.strip(),
            )

    if connections:
        logger.info("Imported %s business connection(s) from txt into JSON", len(connections))
        _write_connections(connections)
        txt_path.unlink(missing_ok=True)

    return connections


def _read_connections() -> dict[int, BusinessConnectionRecord]:
    if not BUSINESS_CONNECTIONS_FILE.is_file():
        return _import_txt_if_needed()

    try:
        raw = json.loads(BUSINESS_CONNECTIONS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.warning("Invalid JSON in %s, treating as empty", BUSINESS_CONNECTIONS_FILE)
        return {}

    if not isinstance(raw, dict):
        return {}

    connections: dict[int, BusinessConnectionRecord] = {}
    for key, value in raw.items():
        try:
            user_id = int(key)
        except TypeError, ValueError:
            continue
        record = _parse_record(value, user_id)
        if record is not None:
            connections[user_id] = record
    return connections


def _write_connections(connections: dict[int, BusinessConnectionRecord]) -> None:
    payload = {
        str(user_id): {"user_id": user_id, "connection_id": record.connection_id}
        for user_id, record in sorted(connections.items())
    }
    BUSINESS_CONNECTIONS_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    logger.info("Saved business connections to %s", BUSINESS_CONNECTIONS_FILE)


def _load_connections() -> dict[int, BusinessConnectionRecord]:
    stored = _read_connections()
    pruned = {uid: record for uid, record in stored.items() if uid in ADMIN_ID}
    if pruned != stored:
        _write_connections(pruned)
    return pruned


def _connection_exists(connection_id: str) -> bool:
    return any(record.connection_id == connection_id for record in _load_connections().values())


def register_connection(connection_id: str, user_id: int) -> None:
    if not is_business_admin(user_id):
        logger.warning(
            "Skipped business connection register for non-admin user_id=%s connection_id=%s",
            user_id,
            connection_id,
        )
        return

    connections = _load_connections()
    connections[user_id] = BusinessConnectionRecord(user_id=user_id, connection_id=connection_id)
    _write_connections(connections)
    logger.info("Registered business connection user_id=%s connection_id=%s", user_id, connection_id)


def is_connection_allowed(connection_id: str) -> bool:
    return _connection_exists(connection_id)


def get_connection_user_id(connection_id: str) -> int | None:
    for user_id, record in _load_connections().items():
        if record.connection_id == connection_id:
            return user_id
    return None


def _extract_bot_connection(result: object) -> types.BotBusinessConnection | None:
    if isinstance(result, types.BotBusinessConnection):
        return result
    if isinstance(result, types.UpdateBotBusinessConnect):
        return result.connection

    connection = getattr(result, "connection", None)
    if isinstance(connection, types.BotBusinessConnection):
        return connection

    updates = getattr(result, "updates", None)
    if updates:
        for update in updates:
            found = _extract_bot_connection(update)
            if found is not None:
                return found
    return None


async def resolve_connection(connection_id: str) -> BusinessConnectionRecord | None:
    from app import Kenzo

    try:
        result = await Kenzo(functions.account.GetBotBusinessConnectionRequest(connection_id=connection_id))
    except Exception as exc:
        logger.warning("Could not resolve business connection %s: %s", connection_id, exc)
        return None

    connection = _extract_bot_connection(result)
    if connection is None:
        return None

    return BusinessConnectionRecord(
        user_id=connection.user_id,
        connection_id=connection.connection_id,
    )


async def ensure_connection_allowed(
    connection_id: str,
    *,
    sender_id: int | None = None,
) -> bool:
    if _connection_exists(connection_id):
        return True

    resolved = await resolve_connection(connection_id)
    if resolved and is_business_admin(resolved.user_id):
        register_connection(resolved.connection_id, resolved.user_id)
        logger.info(
            "Auto-registered business connection user_id=%s connection_id=%s",
            resolved.user_id,
            resolved.connection_id,
        )
        return True

    if is_business_admin(sender_id):
        register_connection(connection_id, sender_id)
        logger.info("Registered business connection from admin sender_id=%s", sender_id)
        return True

    logger.warning(
        "Business connection denied: connection_id=%s sender_id=%s admins=%s file=%s",
        connection_id,
        sender_id,
        ADMIN_ID,
        BUSINESS_CONNECTIONS_FILE,
    )
    return False


def is_admin_business_sender(event: types.UpdateBotNewBusinessMessage, sender_id: int | None) -> bool:
    if is_business_admin(sender_id):
        return True

    message = event.message
    if getattr(message, "out", False):
        owner_id = get_connection_user_id(event.connection_id)
        return is_business_admin(owner_id)

    return False


def get_sender_id(message: types.Message) -> int | None:
    from_id = getattr(message, "from_id", None)
    if from_id is not None and hasattr(from_id, "user_id"):
        return from_id.user_id
    return None
