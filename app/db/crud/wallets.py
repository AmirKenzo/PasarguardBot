from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.future import select

from app.db.base import AsyncSessionLocal as Session
from app.db.models.wallet import Wallet
from app.logger import get_logger

log = get_logger(__name__)


class WalletCRUD:
    async def create_wallet(self, address: str, wallet_type: str, api_key: str | None = None):
        """Create a new wallet"""
        async with Session() as session:
            try:
                # Check if wallet type already exists
                existing = await self.get_wallet_by_type(wallet_type.upper())
                if existing:
                    return None

                new_wallet = Wallet(address=address, type=wallet_type.upper(), api_key=api_key)
                session.add(new_wallet)
                await session.commit()
                return new_wallet
            except SQLAlchemyError as e:
                await session.rollback()
                log.error("Error creating wallet: %s", e, exc_info=e)
                return None

    async def get_all_wallets(self):
        """Get all wallets"""
        async with Session() as session:
            try:
                result = await session.execute(select(Wallet))
                return result.scalars().all()
            except SQLAlchemyError as e:
                log.error("Error retrieving wallets: %s", e, exc_info=e)
                return []

    async def get_wallet_by_type(self, wallet_type: str):
        """Get wallet by type (e.g., 'TRX')"""
        async with Session() as session:
            try:
                result = await session.execute(select(Wallet).filter_by(type=wallet_type.upper()))
                return result.scalars().first()
            except SQLAlchemyError as e:
                log.error("Error retrieving wallet by type: %s", e, exc_info=e)
                return None

    async def get_wallet_by_id(self, wallet_id: int):
        """Get wallet by ID"""
        async with Session() as session:
            try:
                result = await session.execute(select(Wallet).filter_by(id=wallet_id))
                return result.scalars().first()
            except SQLAlchemyError as e:
                log.error("Error retrieving wallet by id: %s", e, exc_info=e)
                return None

    async def update_wallet(
        self, wallet_id: int, address: str | None = None, wallet_type: str | None = None, api_key: str | None = None
    ):
        """Update wallet"""
        async with Session() as session:
            try:
                result = await session.execute(select(Wallet).filter_by(id=wallet_id))
                wallet = result.scalars().first()
                if wallet:
                    if address is not None:
                        wallet.address = address
                    if wallet_type is not None:
                        wallet.type = wallet_type.upper()
                    if api_key is not None:
                        wallet.api_key = api_key
                    await session.commit()
                    return wallet
                return None
            except SQLAlchemyError as e:
                await session.rollback()
                log.error("Error updating wallet: %s", e, exc_info=e)
                return None

    async def delete_wallet(self, wallet_id: int):
        """Delete wallet"""
        async with Session() as session:
            try:
                result = await session.execute(select(Wallet).filter_by(id=wallet_id))
                wallet = result.scalars().first()
                if wallet:
                    await session.delete(wallet)
                    await session.commit()
                    return True
                return False
            except SQLAlchemyError as e:
                await session.rollback()
                log.error("Error deleting wallet: %s", e, exc_info=e)
                return False
