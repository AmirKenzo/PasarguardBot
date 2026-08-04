from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.future import select

from app.db.base import AsyncSessionLocal as Session
from app.db.models.secrets import Secret
from app.logger import get_logger
from app.utils.security.secrets_cache import (
    SECRET_NAMES,
    _cache,
    generate_secret_value,
    get_crypto_key,
    get_webhook_secret,
)

log = get_logger(__name__)

__all__ = [
    "SecretsCRUD",
    "ensure_secrets",
    "get_crypto_key",
    "get_webhook_secret",
]


class SecretsCRUD:
    async def ensure_secrets(self) -> dict[str, str]:
        """Load secrets from DB into process cache; create missing/empty rows with random values.

        Never reads .env / config — migration is the only place that may seed from legacy env.
        """
        loaded: dict[str, str] = {}
        try:
            async with Session() as session:
                result = await session.execute(select(Secret))
                existing = {row.name: row for row in result.scalars().all()}

                for name in SECRET_NAMES:
                    row = existing.get(name)
                    value = (row.value if row else "") or ""
                    if not value.strip():
                        value = generate_secret_value()
                        if row is None:
                            session.add(Secret(name=name, value=value))
                        else:
                            row.value = value
                    _cache[name] = value
                    loaded[name] = value

                await session.commit()
        except SQLAlchemyError as e:
            log.error("Error ensuring secrets", exc_info=e)
            raise

        return loaded


async def ensure_secrets() -> dict[str, str]:
    return await SecretsCRUD().ensure_secrets()
