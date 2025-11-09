"""Database setup for bot and Alembic migrations.

This file:
- strips accidental surrounding quotes from env values
- ensures async/sync driver names
- passes ssl=True to asyncpg via connect_args
- keeps sync engine for Alembic (psycopg2)
"""

from __future__ import annotations

import os
import ssl
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url

# import your config env values (Settings should expose raw URLs)
from bot.config import DATABASE_URL as RAW_DATABASE_URL, DATABASE_URL_SYNC as RAW_DATABASE_URL_SYNC

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
DATABASE_URL_SYNC = _strip_quotes(RAW_DATABASE_URL_SYNC) or DATABASE_URL  # fallback if not provided

# ----------------------
# URL helpers
# ----------------------
def _ensure_async_driver(url: str) -> str:
    """Return DB URL using async driver (asyncpg / aiosqlite)."""
    sa_url = make_url(url)
    # canonicalize postgres names
    if sa_url.drivername in ("postgresql", "postgres"):
        sa_url = sa_url.set(drivername="postgresql+asyncpg")
    elif sa_url.drivername == "sqlite":
        sa_url = sa_url.set(drivername="sqlite+aiosqlite")
    return str(sa_url)


def _ensure_sync_driver(url: str) -> str:
    """Return DB URL using sync driver (psycopg2 / sqlite)."""
    sa_url = make_url(url)
    if sa_url.drivername in ("postgresql+asyncpg", "postgresql+asyncpg://"):
        sa_url = sa_url.set(drivername="postgresql+psycopg2")
    elif sa_url.drivername == "sqlite+aiosqlite":
        sa_url = sa_url.set(drivername="sqlite")
    # if user provided plain 'postgres://' or 'postgresql://', keep it (psycopg2 can parse it)
    return str(sa_url)


# ----------------------
# ASYNC engine (бот: asyncpg)
# ----------------------
# For asyncpg we DON'T use ?sslmode in URL. Instead pass connect_args={"ssl": True}
async_url = _ensure_async_driver(DATABASE_URL)

# create_ssl_context only if needed (optional): default True will use system CA
# If you need custom CA, create ssl.SSLContext and set cafile.
async_connect_args = {"ssl": True}

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
sync_url = _ensure_sync_driver(DATABASE_URL_SYNC)

# If the sync URL already contains ?sslmode=require, psycopg2 will honor it.
# Otherwise we can pass connect_args={"sslmode": "require"} (optional).
sync_connect_args = {}
# enable this if you did NOT put ?sslmode=require in the URL:
# sync_connect_args = {"sslmode": "require"}

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
