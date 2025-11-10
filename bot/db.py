"""Database setup for bot and Alembic migrations.

This file:
- strips accidental surrounding quotes from env values
- ensures async/sync driver names
- passes ssl=True to asyncpg via connect_args
- keeps sync engine for Alembic (psycopg2)
"""

from __future__ import annotations

import ssl
from typing import Optional, cast

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url

# import your config env values (Settings should expose raw URLs)
from bot.config import DATABASE_URL as RAW_DATABASE_URL

# Import your models (adjust import path if needed)
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

# helper - safely strip accidental surrounding quotes
def _strip_quotes(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    s = s.strip()
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    return s

DATABASE_URL = _strip_quotes(RAW_DATABASE_URL)

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL must be configured")

DATABASE_URL = cast(str, DATABASE_URL)

# ----------------------
# URL helpers
# ----------------------
def _ensure_async_driver(url: str) -> str:
    """Return DB URL using async driver (asyncpg / aiosqlite)."""
    sa_url = make_url(url)
    # canonicalize postgres names
    if sa_url.drivername in ("postgresql", "postgres") or sa_url.drivername.startswith("postgresql+"):
        sa_url = sa_url.set(drivername="postgresql+asyncpg")
    elif sa_url.drivername == "sqlite":
        sa_url = sa_url.set(drivername="sqlite+aiosqlite")
    return str(sa_url)


def _ensure_sync_driver(url: str) -> str:
    """Return DB URL using sync driver (psycopg2 / sqlite)."""
    sa_url = make_url(url)
    if (
        sa_url.drivername in ("postgresql", "postgres")
        or sa_url.drivername.startswith("postgresql+")
    ):
        sa_url = sa_url.set(drivername="postgresql+psycopg2")
    elif sa_url.drivername == "sqlite+aiosqlite":
        sa_url = sa_url.set(drivername="sqlite")
    return str(sa_url)


# ----------------------
# ASYNC engine (бот: asyncpg)
# ----------------------
# For asyncpg we DON'T use ?sslmode in URL. Instead pass connect_args={"ssl": True}
async_url = _ensure_async_driver(DATABASE_URL)

# create a permissive TLS context for asyncpg: encryption stays enabled but
# certificate verification is skipped because Render's managed Postgres uses
# self-signed certs in some environments.
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE
async_connect_args = {"ssl": ssl_context}

async_engine = create_async_engine(
    async_url,
    connect_args=async_connect_args,
    echo=False,
    future=True,
)

async_session = async_sessionmaker(
    bind=async_engine,
    expire_on_commit=False,
    class_=AsyncSession,
)

# ----------------------
# SYNC engine (Alembic / backend: psycopg2)
# ----------------------
def get_sync_database_url() -> str:
    """Return sync-safe database URL derived from the configured DATABASE_URL."""

    return _ensure_sync_driver(DATABASE_URL)


sync_url = get_sync_database_url()

# If the sync URL already contains ?sslmode=require, psycopg2 will honor it.
# Otherwise we pass connect_args={"sslmode": "require"} so TLS is used even
# when the URL omits the parameter (Render uses self-signed certs).
sync_connect_args = {"sslmode": "require"}

sync_engine = create_engine(
    sync_url,
    connect_args=sync_connect_args,
    future=True,
)

def get_sync_session() -> sessionmaker:
    return sessionmaker(bind=sync_engine)


# ----------------------
# Инициализация базы (ботом, НЕ Alembic)
# ----------------------
async def init_db() -> None:
    """Create tables if they don't exist (used by the bot on startup)."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


__all__ = [
    "Base",
    "async_engine",
    "sync_engine",
    "async_session",
    "AsyncSession",
    "get_sync_database_url",

    # models:
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
