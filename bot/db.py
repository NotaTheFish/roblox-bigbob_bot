# bot/db.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from bot.config import DATABASE_URL


# ----------------------------
# ASYNC DATABASE INITIALIZER
# ----------------------------

def _make_async_database_url(url: str) -> str:
    sa_url = make_url(url)
    driver = sa_url.drivername

    if "+" in driver:
        return url  # already async

    if driver == "sqlite":
        sa_url = sa_url.set(drivername="sqlite+aiosqlite")
    elif driver == "postgresql":
        sa_url = sa_url.set(drivername="postgresql+asyncpg")
    elif driver == "mysql":
        sa_url = sa_url.set(drivername="mysql+aiomysql")
    else:
        raise RuntimeError(
            "Unsupported DB driver. Use async driver or supported sync (sqlite/postgres/mysql)."
        )

    return str(sa_url)


class Base(AsyncAttrs, DeclarativeBase):
    pass


async_engine: AsyncEngine = create_async_engine(
    _make_async_database_url(DATABASE_URL),
    echo=False
)
async_session = async_sessionmaker(async_engine, expire_on_commit=False)


# ----------------------------
# MODELS
# ----------------------------

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column("telegram_id", unique=True, index=True)
    tg_username: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    username: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    roblox_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)

    # Game stats
    balance: Mapped[int] = mapped_column(Integer, default=0)
    cash: Mapped[int] = mapped_column(Integer, default=0)
    items: Mapped[str] = mapped_column(String, default="")
    level: Mapped[int] = mapped_column(Integer, default=1)


class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    is_root: Mapped[bool] = mapped_column(Boolean, default=False)


class ShopItem(Base):
    __tablename__ = "shop_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String)
    item_type: Mapped[str] = mapped_column(String)
    value: Mapped[str] = mapped_column(String)
    price: Mapped[int] = mapped_column(Integer)


class TopUpRequest(Base):
    __tablename__ = "topup_requests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer)
    amount: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="pending")


class Achievement(Base):
    __tablename__ = "achievements"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String)
    reward: Mapped[int] = mapped_column(Integer)


class UserAchievement(Base):
    __tablename__ = "user_achievements"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(Integer)
    achievement_id: Mapped[int] = mapped_column(Integer)


# ----------------------------
# INIT FUNCTION
# ----------------------------

async def init_db() -> None:
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


__all__ = [
    "async_engine",
    "async_session",
    "init_db",
    "User",
    "Admin",
    "ShopItem",
    "TopUpRequest",
    "Achievement",
    "UserAchievement",
]
