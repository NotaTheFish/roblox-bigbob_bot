"""Database setup for bot and Alembic migrations."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

from bot.config import DATABASE_URL
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
# ✅ ASYNC engine (используется ботом)
# ----------------------
async_engine = create_async_engine(
    DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
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
    DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://"),
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
