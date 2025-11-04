"""Backend configuration shared with the Telegram bot."""
from __future__ import annotations

from functools import lru_cache

from bot.config import DATABASE_URL, get_env


class Settings:
    """Application settings resolved from environment variables."""

    database_url: str = DATABASE_URL
    hmac_secret: str
    idempotency_ttl_seconds: int
    roblox_api_base_url: str
    telegram_payment_secret: str

    def __init__(self) -> None:
        self.hmac_secret = get_env("BACKEND_HMAC_SECRET", required=True)
        self.idempotency_ttl_seconds = int(get_env("BACKEND_IDEMPOTENCY_TTL", "3600"))
        self.roblox_api_base_url = get_env("ROBLOX_API_BASE_URL", "")
        self.telegram_payment_secret = get_env("TELEGRAM_PAYMENT_SECRET", "")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
backend/database.py
Новый
+27
-0

"""Database helpers for the backend package."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import Base, async_engine, async_session


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Provide a transaction scope for database operations."""
    async with async_session() as session:  # type: ignore[call-arg]
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_models() -> None:
    """Ensure backend models are created."""
    async with async_engine.begin() as conn:  # type: ignore[arg-type]
        await conn.run_sync(Base.metadata.create_all)