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