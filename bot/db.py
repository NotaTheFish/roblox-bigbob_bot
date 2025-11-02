# bot/db.py
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import relationship

from bot.config import DATABASE_URL

Base = declarative_base()


# ✅ Преобразование sync URL → async
def _make_async_database_url(url: str) -> str:
    sa_url = make_url(url)
    driver = sa_url.drivername

    if "+" in driver:
        return url

    if driver == "sqlite":
        sa_url = sa_url.set(drivername="sqlite+aiosqlite")
    elif driver == "postgresql":
        sa_url = sa_url.set(drivername="postgresql+asyncpg")
    elif driver == "mysql":
        sa_url = sa_url.set(drivername="mysql+aiomysql")
    else:
        raise RuntimeError(f"Unsupported DB driver {driver}")

    return str(sa_url)


# ✅ Async engine/session
async_engine = create_async_engine(_make_async_database_url(DATABASE_URL), echo=False)
async_session = async_sessionmaker(bind=async_engine, expire_on_commit=False, class_=AsyncSession)


# ✅ MODELS ==================================================================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    tg_id = Column("telegram_id", Integer, unique=True, index=True)
    tg_username = Column(String)
    username = Column(String)
    roblox_id = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    verified = Column(Boolean, default=False)
    code = Column(String)
    is_blocked = Column(Boolean, default=False)

    balance = Column(Integer, default=0)
    cash = Column(Integer, default=0)
    items = Column(Text, default="")
    level = Column(Integer, default=1)


class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True)
    is_root = Column(Boolean, default=False)


class AdminRequest(Base):
    __tablename__ = "admin_requests"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer)
    username = Column(String)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)


class PromoCode(Base):
    __tablename__ = "promocodes"

    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True)
    promo_type = Column(String)  # money / item
    value = Column(String)
    max_uses = Column(Integer, nullable=True)
    uses = Column(Integer, default=0)
    expires_at = Column(DateTime, nullable=True)


class TopUpRequest(Base):
    __tablename__ = "topup_requests"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    amount = Column(Integer)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)


class Achievement(Base):
    __tablename__ = "achievements"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    description = Column(Text)
    reward = Column(Integer, default=0)


class UserAchievement(Base):
    __tablename__ = "user_achievements"

    id = Column(Integer, primary_key=True)
    tg_id = Column(Integer)
    achievement_id = Column(Integer, ForeignKey("achievements.id"))
    earned_at = Column(DateTime, default=datetime.utcnow)


class ShopItem(Base):
    __tablename__ = "shop_items"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    item_type = Column(String)  # money / privilege / item
    value = Column(String)
    price = Column(Integer)


# ✅ DB INIT =================================================================

async def init_db():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
