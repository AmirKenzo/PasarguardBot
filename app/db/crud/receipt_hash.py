import hashlib
import io
import time

from PIL import Image
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from app.db.base import AsyncSessionLocal as Session
from app.db.models.receipt_hash import ReceiptHash

# Normalize to fixed size then content-hash so any pixel change yields different hash.
_CONTENT_HASH_MAX_SIZE = 512


def compute_receipt_phash(image_bytes: bytes | bytearray) -> str | None:
    """Content hash (SHA256 of normalized pixels). Any change in image = different hash.
    Returns 64-char hex or None on error. imagehash stays installed; not used here for accuracy."""
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        w, h = img.size
        if max(w, h) > _CONTENT_HASH_MAX_SIZE:
            ratio = _CONTENT_HASH_MAX_SIZE / max(w, h)
            img = img.resize((int(w * ratio), int(h * ratio)), Image.Resampling.LANCZOS)
        return hashlib.sha256(img.tobytes()).hexdigest()
    except Exception:
        return None


class ReceiptHashCRUD:
    async def try_insert(self, phash: str, user_id: int) -> ReceiptHash | None:
        """Insert phash. Returns ReceiptHash if inserted, None if duplicate (unique constraint)."""
        ts = int(time.time())
        async with Session() as session:
            try:
                row = ReceiptHash(phash=phash, transaction_id=None, user_id=user_id, created_at=ts)
                session.add(row)
                await session.commit()
                return row
            except IntegrityError:
                await session.rollback()
                return None

    async def update_transaction_id(self, phash: str, transaction_id: int) -> bool:
        """Update transaction_id for the receipt_hash row. Returns True if updated."""

        async with Session() as session:
            result = await session.execute(
                update(ReceiptHash).where(ReceiptHash.phash == phash).values(transaction_id=transaction_id)
            )
            await session.commit()
            return result.rowcount is not None and result.rowcount > 0
