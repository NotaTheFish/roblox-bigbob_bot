"""Database models specific to the backend service."""
from __future__ import annotations

from sqlalchemy import BigInteger, Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from bot.db import Base


class GameProgress(Base):
    __tablename__ = "game_progress"

    id = Column(Integer, primary_key=True)
    roblox_user_id = Column(String, index=True, nullable=False)
    progress = Column(JSONB, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    metadata = Column(JSONB)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class GrantEvent(Base):
    __tablename__ = "game_grants"

    id = Column(Integer, primary_key=True)
    roblox_user_id = Column(String, index=True, nullable=False)
    rewards = Column(JSONB, nullable=False)
    source = Column(String, nullable=True)
    request_id = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, nullable=False, index=True)
    endpoint = Column(String, nullable=False)
    status_code = Column(Integer, nullable=True)
    response_body = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)


class PaymentWebhookEvent(Base):
    __tablename__ = "payment_webhooks"

    id = Column(Integer, primary_key=True)
    telegram_payment_id = Column(String, unique=True, nullable=False)
    telegram_user_id = Column(BigInteger, index=True, nullable=False)
    amount = Column(Integer, nullable=False)
    currency = Column(String, nullable=False)
    raw_payload = Column(JSONB, nullable=False)
    status = Column(String, nullable=False, default="received")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)


class RobloxSyncEvent(Base):
    __tablename__ = "roblox_sync_events"

    id = Column(Integer, primary_key=True)
    roblox_user_id = Column(String, index=True, nullable=False)
    action = Column(String, nullable=False)
    payload = Column(JSONB, nullable=False)
    response = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())