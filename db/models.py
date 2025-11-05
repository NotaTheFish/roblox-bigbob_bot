"""SQLAlchemy models shared between the Telegram bot and backend services."""
from __future__ import annotations

from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func


def _generate_request_id() -> str:
    """Generate a short unique identifier suitable for request tracking."""
    return uuid4().hex


Base = declarative_base()


@compiles(JSONB, "sqlite")
def _compile_jsonb_for_sqlite(_type, compiler, **kwargs):
    """Render JSONB columns as JSON for SQLite compatibility."""
    return "JSON"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    tg_id = Column("telegram_id", BigInteger, unique=True, index=True, nullable=False)
    tg_username = Column(String(255))
    username = Column(String(255))
    roblox_id = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    verified = Column(Boolean, default=False, nullable=False)
    code = Column(String(64))
    is_blocked = Column(Boolean, default=False, nullable=False)
    balance = Column(Integer, default=0, nullable=False)
    cash = Column(Integer, default=0, nullable=False)
    items = Column(Text)
    level = Column(Integer, default=1, nullable=False)
    referral_code = Column(String(64), unique=True, index=True)
    referred_at = Column(DateTime(timezone=True))

    achievements = relationship("UserAchievement", back_populates="user")
    referrals = relationship("Referral", back_populates="referrer", foreign_keys="Referral.referrer_id")
    referred_referral = relationship(
        "Referral",
        back_populates="referred",
        foreign_keys="Referral.referred_id",
        uselist=False,
    )
    referral_rewards = relationship(
        "ReferralReward",
        back_populates="referrer",
        foreign_keys="ReferralReward.referrer_id",
    )
    purchases = relationship("Purchase", back_populates="user")
    payments = relationship("Payment", back_populates="user")
    withdrawals = relationship("Withdrawal", back_populates="user")
    promocode_redemptions = relationship("PromocodeRedemption", back_populates="user")
    topup_requests = relationship("TopUpRequest", back_populates="user")
    logs = relationship("LogEntry", back_populates="user")


class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    is_root = Column(Boolean, default=False, nullable=False)


class AdminRequest(Base):
    __tablename__ = "admin_requests"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, index=True, nullable=False)
    username = Column(String(255))
    status = Column(String(32), default="pending", nullable=False)
    request_id = Column(String(64), unique=True, nullable=False, default=_generate_request_id)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PromoCode(Base):
    __tablename__ = "promocodes"

    id = Column(Integer, primary_key=True)
    code = Column(String(64), unique=True, nullable=False, index=True)
    description = Column(Text)
    promo_type = Column(String(32), default="money", nullable=False)
    value = Column(String(255))
    reward_amount = Column(Integer, default=0, nullable=False)
    reward_type = Column(String(32), default="balance", nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    max_uses = Column(Integer)
    uses = Column(Integer, default=0, nullable=False)
    expires_at = Column(DateTime(timezone=True))
    metadata_json = Column("metadata", JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    redemptions = relationship("PromocodeRedemption", back_populates="promocode")


class Achievement(Base):
    __tablename__ = "achievements"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False)
    description = Column(Text)
    reward = Column(Integer, nullable=False)

    user_achievements = relationship("UserAchievement", back_populates="achievement")


class UserAchievement(Base):
    __tablename__ = "user_achievements"

    id = Column(Integer, primary_key=True)
    tg_id = Column(BigInteger, index=True, nullable=False)
    achievement_id = Column(Integer, ForeignKey("achievements.id"), nullable=False)
    earned_at = Column(DateTime(timezone=True), server_default=func.now())

    achievement = relationship("Achievement", back_populates="user_achievements")
    user = relationship(
        "User",
        primaryjoin="User.tg_id == UserAchievement.tg_id",
        viewonly=True,
    )


class Server(Base):
    __tablename__ = "servers"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(64), unique=True, nullable=False, index=True)
    telegram_chat_id = Column(BigInteger, unique=True)
    description = Column(Text)
    status = Column(String(32), default="active", nullable=False)
    metadata_json = Column("metadata", JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    products = relationship("Product", back_populates="server")
    logs = relationship("LogEntry", back_populates="server")


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    server_id = Column(Integer, ForeignKey("servers.id"))
    slug = Column(String(128), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    item_type = Column(String(32), nullable=False)
    value = Column(String(255))
    price = Column(Integer, nullable=False)
    currency = Column(String(16), nullable=False, default="coins")
    status = Column(String(32), default="active", nullable=False)
    per_user_limit = Column(Integer)
    stock_limit = Column(Integer)
    referral_bonus = Column(Integer, default=0, nullable=False)
    metadata_json = Column("metadata", JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    server = relationship("Server", back_populates="products")
    purchases = relationship("Purchase", back_populates="product")

    __table_args__ = (UniqueConstraint("server_id", "slug", name="uq_products_server_slug"),)


class Purchase(Base):
    __tablename__ = "purchases"

    id = Column(Integer, primary_key=True)
    request_id = Column(String(64), unique=True, nullable=False, default=_generate_request_id)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    telegram_id = Column(BigInteger, index=True, nullable=False)
    server_id = Column(Integer, ForeignKey("servers.id"))
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, default=1, nullable=False)
    unit_price = Column(Integer, nullable=False)
    total_price = Column(Integer, nullable=False)
    status = Column(String(32), default="pending", nullable=False)
    notes = Column(Text)
    metadata_json = Column("metadata", JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True))

    user = relationship("User", back_populates="purchases")
    server = relationship("Server")
    product = relationship("Product", back_populates="purchases")
    payment = relationship("Payment", back_populates="purchase", uselist=False)
    referral_rewards = relationship("ReferralReward", back_populates="purchase")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True)
    request_id = Column(String(64), unique=True, nullable=False, default=_generate_request_id)
    provider = Column(String(64), nullable=False)
    provider_payment_id = Column(String(128), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    telegram_id = Column(BigInteger, index=True)
    purchase_id = Column(Integer, ForeignKey("purchases.id"))
    amount = Column(Integer, nullable=False)
    currency = Column(String(16), nullable=False)
    status = Column(String(32), default="received", nullable=False)
    metadata_json = Column("metadata", JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True))

    user = relationship("User", back_populates="payments")
    purchase = relationship("Purchase", back_populates="payment")
    topup_request = relationship("TopUpRequest", back_populates="payment", uselist=False)
    webhook_events = relationship("PaymentWebhookEvent", back_populates="payment")
    referral_rewards = relationship("ReferralReward", back_populates="payment")


class PaymentWebhookEvent(Base):
    __tablename__ = "payment_webhooks"

    id = Column(Integer, primary_key=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), index=True)
    telegram_payment_id = Column(String(128), nullable=False, unique=True)
    telegram_user_id = Column(BigInteger, nullable=False, index=True)
    amount = Column(Integer, nullable=False)
    currency = Column(String(16), nullable=False)
    raw_payload = Column(JSONB, nullable=False)
    status = Column(String(32), default="received", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True))

    payment = relationship("Payment", back_populates="webhook_events")

    __table_args__ = (
        UniqueConstraint("telegram_payment_id", name="uq_payment_webhooks_telegram_payment_id"),
    )


class Withdrawal(Base):
    __tablename__ = "withdrawals"

    id = Column(Integer, primary_key=True)
    request_id = Column(String(64), unique=True, nullable=False, default=_generate_request_id)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    telegram_id = Column(BigInteger, index=True, nullable=False)
    amount = Column(Integer, nullable=False)
    status = Column(String(32), default="pending", nullable=False)
    method = Column(String(64))
    destination = Column(String(255))
    metadata_json = Column("metadata", JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True))

    user = relationship("User", back_populates="withdrawals")


class PromocodeRedemption(Base):
    __tablename__ = "promocode_redemptions"

    id = Column(Integer, primary_key=True)
    request_id = Column(String(64), unique=True, nullable=False, default=_generate_request_id)
    promocode_id = Column(Integer, ForeignKey("promocodes.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    telegram_id = Column(BigInteger, index=True, nullable=False)
    reward_amount = Column(Integer)
    reward_type = Column(String(32))
    metadata_json = Column("metadata", JSONB)
    redeemed_at = Column(DateTime(timezone=True), server_default=func.now())

    promocode = relationship("PromoCode", back_populates="redemptions")
    user = relationship("User", back_populates="promocode_redemptions")

    __table_args__ = (UniqueConstraint("promocode_id", "user_id", name="uq_promocode_user"),)


class Referral(Base):
    __tablename__ = "referrals"

    id = Column(Integer, primary_key=True)
    referrer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    referrer_telegram_id = Column(BigInteger, nullable=False, index=True)
    referred_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    referred_telegram_id = Column(BigInteger, nullable=False, index=True)
    referral_code = Column(String(64), nullable=False, index=True)
    metadata_json = Column("metadata", JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    referrer = relationship("User", back_populates="referrals", foreign_keys=[referrer_id])
    referred = relationship("User", back_populates="referred_referral", foreign_keys=[referred_id])
    rewards = relationship("ReferralReward", back_populates="referral")

    __table_args__ = (UniqueConstraint("referrer_id", "referred_id", name="uq_referral_pair"),)


class ReferralReward(Base):
    __tablename__ = "referral_rewards"

    id = Column(Integer, primary_key=True)
    referral_id = Column(Integer, ForeignKey("referrals.id"), nullable=False)
    referrer_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    purchase_id = Column(Integer, ForeignKey("purchases.id"), nullable=False)
    payment_id = Column(Integer, ForeignKey("payments.id"))
    amount = Column(Integer, nullable=False)
    status = Column(String(32), default="pending", nullable=False)
    metadata_json = Column("metadata", JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    granted_at = Column(DateTime(timezone=True))

    referral = relationship("Referral", back_populates="rewards")
    referrer = relationship("User", back_populates="referral_rewards")
    purchase = relationship("Purchase", back_populates="referral_rewards")
    payment = relationship("Payment", back_populates="referral_rewards")


class LogEntry(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True)
    request_id = Column(String(64), index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    telegram_id = Column(BigInteger, index=True)
    server_id = Column(Integer, ForeignKey("servers.id"))
    event_type = Column(String(64), nullable=False)
    message = Column(Text)
    data = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="logs")
    server = relationship("Server", back_populates="logs")


class TopUpRequest(Base):
    __tablename__ = "topup_requests"

    id = Column(Integer, primary_key=True)
    request_id = Column(String(64), unique=True, nullable=False, default=_generate_request_id)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    telegram_id = Column(BigInteger, index=True, nullable=False)
    amount = Column(Integer, nullable=False)
    currency = Column(String(16), nullable=False, default="rub")
    status = Column(String(32), default="pending", nullable=False)
    metadata_json = Column("metadata", JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    payment_id = Column(Integer, ForeignKey("payments.id"))

    user = relationship("User", back_populates="topup_requests")
    payment = relationship("Payment", back_populates="topup_request")


class GameProgress(Base):
    __tablename__ = "game_progress"

    id = Column(Integer, primary_key=True)
    roblox_user_id = Column(String(255), index=True, nullable=False)
    progress = Column(JSONB, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    metadata_json = Column("metadata", JSONB)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class GrantEvent(Base):
    __tablename__ = "game_grants"

    id = Column(Integer, primary_key=True)
    roblox_user_id = Column(String(255), index=True, nullable=False)
    rewards = Column(JSONB, nullable=False)
    source = Column(String(255))
    request_id = Column(String(64), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class RobloxSyncEvent(Base):
    __tablename__ = "roblox_sync_events"

    id = Column(Integer, primary_key=True)
    roblox_user_id = Column(String(255), index=True, nullable=False)
    action = Column(String(255), nullable=False)
    payload = Column(JSONB, nullable=False)
    response = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    id = Column(Integer, primary_key=True)
    key = Column(String(255), unique=True, nullable=False, index=True)
    endpoint = Column(String(255), nullable=False)
    status_code = Column(Integer)
    response_body = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
