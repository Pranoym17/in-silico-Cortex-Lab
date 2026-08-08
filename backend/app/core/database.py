from collections.abc import AsyncGenerator

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine = create_async_engine(settings.database_url, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


def create_worker_engine() -> AsyncEngine:
    """Return an engine owned by one Celery task's asyncio loop.

    Celery's Windows solo worker calls ``asyncio.run`` per task. Reusing a
    pooled asyncpg connection from a prior closed loop causes transport errors.
    """
    return create_async_engine(settings.database_url, poolclass=pool.NullPool, pool_pre_ping=True)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

