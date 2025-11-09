"""Database setup for bot and Alembic migrations."""

from __future__ import annotations

import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url

from bot.config import DATABASE_URL

DATABASE_URL_SYNC_OVERRIDE = os.getenv("DATABASE_URL_SYNC")
from db import (
    Base,
    Achievement,
    Admin,
    AdminRequest,
    GameProgress,
    GrantEvent,
    IdempotencyKey,
    LogEntry,
    Payment,
    PaymentWebhookEvent,
    Product,
    PromoCode,
    PromocodeRedemption,
    Purchase,
    Referral,
    ReferralReward,
    RobloxSyncEvent,
    Server,
    TopUpRequest,
    User,
    UserAchievement,
    Withdrawal,
)

# ----------------------
# ✅ URL helpers
# ----------------------
def _ensure_async_driver(url: str) -> str:
    """Return a database URL that uses an async driver where possible."""

    sa_url = make_url(url)

    if sa_url.drivername == "postgresql":
        sa_url = sa_url.set(drivername="postgresql+asyncpg")
    elif sa_url.drivername == "sqlite":
        sa_url = sa_url.set(drivername="sqlite+aiosqlite")

    return str(sa_url)


def _ensure_sync_driver(url: str) -> str:
    """Return a database URL that uses a sync driver where possible."""

    sa_url = make_url(url)

    if sa_url.drivername == "postgresql+asyncpg":
        sa_url = sa_url.set(drivername="postgresql")
    elif sa_url.drivername == "sqlite+aiosqlite":
        sa_url = sa_url.set(drivername="sqlite")

    return str(sa_url)


# ----------------------
# ✅ ASYNC engine (используется ботом)
# ----------------------
async_engine = create_async_engine(
    _ensure_async_driver(DATABASE_URL),
    echo=False,
    future=True,
)

async_session = async_sessionmaker(
    bind=async_engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


# ----------------------
# ✅ SYNC engine (используется Alembic миграциями)
# ----------------------
sync_engine = create_engine(
    _ensure_sync_driver(DATABASE_URL_SYNC_OVERRIDE or DATABASE_URL),
    future=True,
)


def get_sync_session() -> sessionmaker:
    return sessionmaker(bind=sync_engine)


# ----------------------
# ✅ Инициализация базы (ботом, НЕ Alembic)
# ----------------------
async def init_db() -> None:
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


__all__ = [
    "Base",
    "async_engine",
    "sync_engine",
    "async_session",
    "AsyncSession",

    # Models:
    "Achievement",
    "Admin",
    "AdminRequest",
    "GameProgress",
    "GrantEvent",
    "IdempotencyKey",
    "LogEntry",
    "Payment",
    "PaymentWebhookEvent",
    "Product",
    "PromoCode",
    "PromocodeRedemption",
    "Purchase",
    "Referral",
    "ReferralReward",
    "RobloxSyncEvent",
    "Server",
    "TopUpRequest",
    "User",
    "UserAchievement",
    "Withdrawal",
]
