# bot/db.py
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from bot.config import DATABASE_URL

Base = declarative_base()
engine = create_engine(DATABASE_URL, echo=False)

# ⚠️ ВАЖНО: expire_on_commit=False — чтобы можно было читать объект после commit
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

# ---------------------
#   MODELS
# ---------------------

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
        tg_id = Column("telegram_id", Integer, unique=True, index=True)
    tg_username = Column(String, nullable=True)
    username = Column(String, nullable=True)
    roblox_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    verified = Column(Boolean, default=False)
    code = Column(String, nullable=True)

    is_blocked = Column(Boolean, default=False)


    # Game stats
    balance = Column(Integer, default=0)
    cash = Column(Integer, default=0)
    items = Column(String, default="")
    level = Column(Integer, default=1)
    play_time = Column(Integer, default=0)
    referrals = Column(Integer, default=0)

    @property
    def roblox_user(self):
        return self.username

    @roblox_user.setter
    def roblox_user(self, value):
        self.username = value


class Server(Base):
    __tablename__ = "servers"

    id = Column(Integer, primary_key=True, index=True)
    number = Column(Integer, unique=True)
    link = Column(String, nullable=True)
    closed_message = Column(String, default="Сервер закрыт")


class PromoCode(Base):
    __tablename__ = "promocodes"

    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True, index=True)
    promo_type = Column(String)           # 'value' / 'discount'
    value = Column(Integer, nullable=True)
    max_uses = Column(Integer, nullable=True)
    uses = Column(Integer, default=0)
    active = Column(Boolean, default=True)

    # ✅ ДОБАВЛЕНО ДЛЯ /expires_at/
    expires_at = Column(DateTime, nullable=True)


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    price = Column(Integer, default=0)

    # ✅ Исправлено: заменяем available → is_active
    is_active = Column(Boolean, default=True)

    # Категория товара (если нужно)
    category = Column(String, nullable=True)

# --- Admin system models ---

class Admin(Base):
    __tablename__ = "admins"
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, index=True)
    is_root = Column(Boolean, default=False)  # Главный админ

class AdminRequest(Base):
    __tablename__ = "admin_requests"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, index=True)
    username = Column(String)
    status = Column(String, default="pending")  # pending / approved / denied

class ShopItem(Base):
    __tablename__ = "shop_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String)
    item_type = Column(String)  # money | privilege | item
    value = Column(String)  # amount of money OR item id OR privilege name
    price = Column(Integer)  # game coins

class TopUpRequest(Base):
    __tablename__ = "topup_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer)
    amount = Column(Integer)
    currency = Column(String)  # rub / uah / usd / crypto etc.
    status = Column(String, default="pending")  # pending / approved / denied

class Achievement(Base):
    __tablename__ = "achievements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String)
    description = Column(String)
    reward = Column(Integer)  # reward in coins

class UserAchievement(Base):
    __tablename__ = "user_achievements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tg_id = Column(Integer)
    achievement_id = Column(Integer)

# ---------------------
# CREATE TABLES
# ---------------------

Base.metadata.create_all(engine)


def run_schema_migrations():
    with engine.begin() as conn:
        columns = {row[1] for row in conn.execute(text("PRAGMA table_info(users)"))}

        if "tg_username" not in columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN tg_username TEXT"))

        if "username" not in columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN username TEXT"))
            if "roblox_user" in columns:
                conn.execute(text("UPDATE users SET username = roblox_user WHERE username IS NULL"))

        if "roblox_id" not in columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN roblox_id TEXT"))

        if "created_at" not in columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN created_at DATETIME"))
            conn.execute(text("UPDATE users SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"))


run_schema_migrations()
