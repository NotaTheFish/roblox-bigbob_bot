# bot/db.py
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from bot.config import DATABASE_URL

Base = declarative_base()
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)
session = SessionLocal()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True)
    roblox_user = Column(String, nullable=True)
    code = Column(String, nullable=True)  # ✅ Код для верификации Roblox
    verified = Column(Boolean, default=False)

    balance = Column(Integer, default=0)
    cash = Column(Integer, default=0)
    items = Column(String, default="")
    level = Column(Integer, default=1)
    play_time = Column(Integer, default=0)
    referrals = Column(Integer, default=0)

    # ВАЖНО: код для верификации
    code = Column(String, nullable=True)

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
    promo_type = Column(String)             # 'value' / 'discount' / 'admin' / ...
    value = Column(Integer, nullable=True)  # число (например, орешки/скидка)
    max_uses = Column(Integer, nullable=True)
    uses = Column(Integer, default=0)
    active = Column(Boolean, default=True)

class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    price = Column(Integer, default=0)
    available = Column(Boolean, default=True)

Base.metadata.create_all(engine)
