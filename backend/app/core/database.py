"""Database session management."""

import ssl
from collections.abc import AsyncGenerator
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import get_settings


class Base(DeclarativeBase):
    pass


def _postgres_connect_args(database_url: str) -> dict:
    """Build asyncpg SSL settings compatible with Railway Postgres."""
    hostname = urlparse(database_url).hostname or ""
    if hostname.endswith(".railway.internal"):
        return {}
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    return {"ssl": ssl_context}


settings = get_settings()
engine_kwargs: dict = {"echo": settings.app_env == "development"}
if settings.database_url.startswith("postgresql+asyncpg://"):
    engine_kwargs["pool_pre_ping"] = True
    connect_args = _postgres_connect_args(settings.database_url)
    if connect_args:
        engine_kwargs["connect_args"] = connect_args
engine = create_async_engine(settings.database_url, **engine_kwargs)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
