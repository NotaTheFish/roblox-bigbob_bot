"""Database configuration for the bot."""

from __future__ import annotations

import os
import ssl
from typing import Optional

from sqlalchemy.engine.url import URL, make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

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


def _get_base_url() -> URL:
    raw_url = os.getenv("DATABASE_URL")
    if not raw_url:
        raise RuntimeError("DATABASE_URL not found")
    return make_url(raw_url)


def to_async_url(url: Optional[URL] = None) -> str:
    base_url = url or BASE_DATABASE_URL
    return base_url.set(drivername="postgresql+asyncpg").render_as_string(hide_password=False)


def to_sync_url(url: Optional[URL] = None) -> str:
    base_url = url or BASE_DATABASE_URL
    return base_url.set(drivername="postgresql+psycopg2").render_as_string(hide_password=False)


BASE_DATABASE_URL = _get_base_url()
ASYNC_DATABASE_URL = to_async_url(BASE_DATABASE_URL)
SYNC_DATABASE_URL = to_sync_url(BASE_DATABASE_URL)

_ssl_context = ssl.create_default_context()
_ssl_context.check_hostname = False
_ssl_context.verify_mode = ssl.CERT_NONE

async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    connect_args={"ssl": _ssl_context},
)

async_session = async_sessionmaker(
    async_engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def init_db() -> None:
    """Create tables if they do not exist."""

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


__all__ = [
    "Base",
    "BASE_DATABASE_URL",
    "ASYNC_DATABASE_URL",
    "SYNC_DATABASE_URL",
    "to_async_url",
    "to_sync_url",
    "async_engine",
    "async_session",
    "AsyncSession",
    "init_db",
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
