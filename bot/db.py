# bot/db.py
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from bot.config import DATABASE_URL
import datetime

Base = declarative_base()
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)
session = SessionLocal()  # можно использовать для быстрых операций

# --- Пользователи ---
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True)
    roblox_user = Column(String, nullable=True)
    verified = Column(Boolean, default=False)
    balance = Column(Integer, default=0)      # баланс в орешках
    cash = Column(Integer, default=0)         # внутриигровой кеш
    items = Column(String, default="")        # строка с предметами через запятую
    level = Column(Integer, default=1)
    play_time = Column(Integer, default=0)    # суммарное время игры в минутах
    referrals = Column(Integer, default=0)

# --- Серверы Roblox ---
class Server(Base):
    __tablename__ = "servers"
    id = Column(Integer, primary_key=True, index=True)
    number = Column(Integer, unique=True)
    link = Column(String, nullable=True)
    closed_message = Column(String, default="Сервер закрыт")

# --- Промокоды ---
class PromoCode(Base):
    __tablename__ = "promocodes"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True)
    type = Column(String)           # кеш, предмет, скидка, админ
    value = Column(Integer, default=0)  # количество кеша, id предмета, процент скидки
    uses = Column(Integer, default=0)
    max_uses = Column(Integer, default=0)  # 0 = безлимит
    expires_at = Column(DateTime, nullable=True)  # дата окончания действия

# --- Магазин внутриигровых предметов ---
class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    price = Column(Integer)        # цена в орешках
    available = Column(Boolean, default=True)

# --- Создание всех таблиц ---
Base.metadata.create_all(engine)
