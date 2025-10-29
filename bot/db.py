# bot/db.py
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from bot.config import DATABASE_URL  # убедись, что импорт из bot.config

Base = declarative_base()
engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)

# Опционально, глобальная сессия для удобства импорта
session = SessionLocal()

# --- Модель пользователя ---
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True)
    roblox_user = Column(String, nullable=True)
    verified = Column(Boolean, default=False)

    # Дополнительные поля для функционала бота
    balance = Column(Integer, default=0)           # баланс в орешках
    cash = Column(Integer, default=0)              # кеш
    items = Column(String, default="")             # строка с предметами через запятую
    level = Column(Integer, default=1)             # уровень персонажа
    play_time = Column(Integer, default=0)         # суммарное время в игре (в минутах)
    referrals = Column(Integer, default=0)         # количество приглашённых

# --- Модель сервера ---
class Server(Base):
    __tablename__ = "servers"
    id = Column(Integer, primary_key=True, index=True)
    number = Column(Integer, unique=True)          # номер сервера (1–5)
    link = Column(String, default=None)            # ссылка на приватный сервер
    closed_message = Column(String, default="Сервер закрыт")  # сообщение при закрытом сервере

# Создание всех таблиц
Base.metadata.create_all(bind=engine)

