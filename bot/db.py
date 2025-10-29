# bot/db.py
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from bot.config import DATABASE_URL

Base = declarative_base()
engine = create_engine(DATABASE_URL, echo=False)

# Важно: отключаем истечение атрибутов после commit, чтобы объекты можно было читать и после закрытия сессии
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

# ---------- Модели ----------

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True)
    roblox_user = Column(String, nullable=True)
    verified = Column(Boolean, default=False)

    # Код верификации для Roblox (ОДНО поле, без дублей)
    code = Column(String, nullable=True)

    # Игровая/бот-статистика
    balance = Column(Integer, default=0)      # орешки в боте
    cash = Column(Integer, default=0)         # внутриигровой кеш
    items = Column(String, default="")        # можно хранить CSV/JSON строкой
    level = Column(Integer, default=1)
    play_time = Column(Integer, default=0)    # минуты
    referrals = Column(Integer, default=0)

class Server(Base):
    __tablename__ = "servers"

    id = Column(Integer, primary_key=True, index=True)
    number = Column(Integer, unique=True)      # 1,2,3...
    link = Column(String, nullable=True)       # ссылка на приватный сервер
    closed_message = Column(String, default="Сервер закрыт")

class PromoCode(Base):
    __tablename__ = "promocodes"

    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True, index=True)
    promo_type = Column(String)                # 'value' / 'discount' / 'admin' / ...
    value = Column(Integer, nullable=True)     # число (орешки/скидка и т.п.)
    max_uses = Column(Integer, nullable=True)  # None = безлимитно
    uses = Column(Integer, default=0)
    active = Column(Boolean, default=True)

class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    price = Column(Integer, default=0)
    available = Column(Boolean, default=True)

    # Добавляем категорию, т.к. код её ожидает
    # ('cash' | 'privilege' | 'stuff' и т.п.)
    category = Column(String, nullable=True)

# Создаём таблицы
Base.metadata.create_all(engine)
