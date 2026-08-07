# from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from config import (
    SQLALCHEMY_DATABASE_URL,
    SQLALCHEMY_MAX_OVERFLOW,
    SQLALCHEMY_POOL_SIZE,
    SQLALCHEMY_POOL_TIMEOUT,
)

Base = declarative_base()


IS_SQLITE = SQLALCHEMY_DATABASE_URL.startswith("sqlite")

if IS_SQLITE:
    engine = create_async_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_async_engine(
        SQLALCHEMY_DATABASE_URL,
        pool_size=SQLALCHEMY_POOL_SIZE,
        max_overflow=SQLALCHEMY_MAX_OVERFLOW,
        pool_recycle=300,
        pool_timeout=SQLALCHEMY_POOL_TIMEOUT,
        pool_pre_ping=True,
        # echo=ECHO_SQL_QUERIES,
    )


AsyncSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)

# Determine dialect once at startup based on connection URL
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    DATABASE_DIALECT = "sqlite"
elif SQLALCHEMY_DATABASE_URL.startswith("postgresql"):
    DATABASE_DIALECT = "postgresql"
elif SQLALCHEMY_DATABASE_URL.startswith("mysql"):
    DATABASE_DIALECT = "mysql"
else:
    raise ValueError("Unsupported database URL")


class GetDB:  # Context Manager
    def __init__(self):
        self.db = AsyncSessionLocal()

    async def __aenter__(self):
        return self.db

    async def __aexit__(self, exc_type, exc_value, traceback):
        if exc_value is not None:
            await self.db.rollback()  # rollback on exception

        await self.db.close()


async def get_db():  # Dependency
    async with GetDB() as db:
        yield db
