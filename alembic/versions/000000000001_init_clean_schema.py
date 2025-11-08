"""Init clean schema - drop all and recreate

Revision ID: 000000000001
Revises: 
Create Date: 2025-11-08 00:00:00.000000

This migration will DROP existing tables (if present) and create fresh ones.
**THIS WILL DESTROY ALL DATA IN THE DROPPED TABLES.**
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "000000000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # --- DROP existing tables if they exist (CASCADE to remove FK dependencies) ---
    # Order doesn't matter because of CASCADE, but we list common names.
    tables = [
        "idempotency_keys",
        "roblox_sync_events",
        "payment_webhooks",
        "game_grants",
        "game_progress",
        "topup_requests",
        "logs",
        "referral_rewards",
        "referrals",
        "promocode_redemptions",
        "withdrawals",
        "payments",
        "purchases",
        "products",
        "servers",
        "user_achievements",
        "achievements",
        "promocodes",
        "admin_requests",
        "admins",
        "users",
    ]

    for t in tables:
        op.execute(sa.text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))

    # --- Create tables (clean) ---
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False, unique=True, index=True),
        sa.Column("telegram_username", sa.String(length=255)),
        sa.Column("username", sa.String(length=255)),
        sa.Column("roblox_id", sa.String(length=255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("code", sa.String(length=64)),
        sa.Column("is_blocked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("balance", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cash", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("items", sa.Text()),
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("referral_code", sa.String(length=64), unique=True),
        sa.Column("referred_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "admins",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("is_root", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "admin_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("username", sa.String(length=255)),
        sa.Column("full_name", sa.String(length=255)),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("request_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "promocodes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=64), nullable=False, unique=True),
        sa.Column("description", sa.Text()),
        sa.Column("promo_type", sa.String(length=32), nullable=False, server_default=sa.text("'money'")),
        sa.Column("value", sa.String(length=255)),
        sa.Column("reward_amount", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reward_type", sa.String(length=32), nullable=False, server_default=sa.text("'balance'")),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("max_uses", sa.Integer()),
        sa.Column("uses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("metadata", sa.dialects.postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.text("now()")),
    )

    op.create_table(
        "achievements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False, unique=True),
        sa.Column("description", sa.Text()),
        sa.Column("reward", sa.Integer(), nullable=False),
    )

    op.create_table(
        "user_achievements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("achievement_id", sa.Integer(), sa.ForeignKey("achievements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("earned_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "servers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False, unique=True),
        sa.Column("telegram_chat_id", sa.BigInteger(), unique=True),
        sa.Column("description", sa.Text()),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'active'")),
        sa.Column("metadata", sa.dialects.postgresql.JSONB()),
        sa.Column("url", sa.String(length=2048)),
        sa.Column("closed_message", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.text("now()")),
    )

    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("server_id", sa.Integer(), sa.ForeignKey("servers.id", ondelete="SET NULL")),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("item_type", sa.String(length=32), nullable=False),
        sa.Column("value", sa.String(length=255)),
        sa.Column("price", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=16), nullable=False, server_default=sa.text("'coins'")),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'active'")),
        sa.Column("per_user_limit", sa.Integer()),
        sa.Column("stock_limit", sa.Integer()),
        sa.Column("referral_bonus", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata", sa.dialects.postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.text("now()")),
    )
    op.create_unique_constraint("uq_products_server_slug", "products", ["server_id", "slug"])

    op.create_table(
        "purchases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("server_id", sa.Integer(), sa.ForeignKey("servers.id", ondelete="SET NULL")),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Integer(), nullable=False),
        sa.Column("total_price", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("notes", sa.Text()),
        sa.Column("metadata", sa.dialects.postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_payment_id", sa.String(length=128), nullable=False, unique=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), index=True),
        sa.Column("telegram_id", sa.BigInteger(), index=True),
        sa.Column("purchase_id", sa.Integer(), sa.ForeignKey("purchases.id", ondelete="SET NULL")),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'received'")),
        sa.Column("metadata", sa.dialects.postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "payment_webhooks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.id", ondelete="CASCADE"), index=True),
        sa.Column("telegram_payment_id", sa.String(length=128), nullable=False, unique=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=16), nullable=False),
        sa.Column("raw_payload", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'received'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
    )
    op.create_unique_constraint("uq_payment_webhooks_telegram_payment_id", "payment_webhooks", ["telegram_payment_id"])

    op.create_table(
        "withdrawals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("telegram_id", sa.BigInteger(), index=True, nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("method", sa.String(length=64)),
        sa.Column("destination", sa.String(length=255)),
        sa.Column("metadata", sa.dialects.postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "promocode_redemptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column("promocode_id", sa.Integer(), sa.ForeignKey("promocodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), index=True, nullable=False),
        sa.Column("reward_amount", sa.Integer()),
        sa.Column("reward_type", sa.String(length=32)),
        sa.Column("metadata", sa.dialects.postgresql.JSONB()),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_unique_constraint("uq_promocode_user", "promocode_redemptions", ["promocode_id", "user_id"])

    op.create_table(
        "referrals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("referrer_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("referrer_telegram_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("referred_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("referred_telegram_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("referral_code", sa.String(length=64), nullable=False, index=True),
        sa.Column("metadata", sa.dialects.postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_unique_constraint("uq_referral_pair", "referrals", ["referrer_id", "referred_id"])

    op.create_table(
        "referral_rewards",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("referral_id", sa.Integer(), sa.ForeignKey("referrals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("referrer_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("purchase_id", sa.Integer(), sa.ForeignKey("purchases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.id", ondelete="SET NULL")),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("metadata", sa.dialects.postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("granted_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_id", sa.String(length=64), index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("telegram_id", sa.BigInteger(), index=True),
        sa.Column("server_id", sa.Integer(), sa.ForeignKey("servers.id", ondelete="CASCADE")),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text()),
        sa.Column("data", sa.dialects.postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "topup_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("telegram_id", sa.BigInteger(), index=True, nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=16), nullable=False, server_default=sa.text("'rub'")),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("metadata", sa.dialects.postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.text("now()")),
        sa.Column("payment_id", sa.Integer(), sa.ForeignKey("payments.id", ondelete="SET NULL")),
    )

    op.create_table(
        "game_progress",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("roblox_user_id", sa.String(length=255), index=True, nullable=False),
        sa.Column("progress", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("metadata", sa.dialects.postgresql.JSONB()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), onupdate=sa.text("now()")),
    )

    op.create_table(
        "game_grants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("roblox_user_id", sa.String(length=255), index=True, nullable=False),
        sa.Column("rewards", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("source", sa.String(length=255)),
        sa.Column("request_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "roblox_sync_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("roblox_user_id", sa.String(length=255), index=True, nullable=False),
        sa.Column("action", sa.String(length=255), nullable=False),
        sa.Column("payload", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("response", sa.dialects.postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=255), nullable=False, index=True, unique=True),
        sa.Column("endpoint", sa.String(length=255), nullable=False),
        sa.Column("status_code", sa.Integer()),
        sa.Column("response_body", sa.dialects.postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )

    # Indexes/constraints that may be needed beyond column definitions
    op.execute(sa.text('DROP INDEX IF EXISTS "ix_users_telegram_id"'))
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"])
    op.create_index("ix_user_achievements_user_id", "user_achievements", ["user_id"])
    op.create_index("ix_products_server_id", "products", ["server_id"])
    op.create_index("ix_purchases_user_id", "purchases", ["user_id"])


def downgrade():
    # drop everything we created
    drop_order = [
        "idempotency_keys",
        "roblox_sync_events",
        "payment_webhooks",
        "game_grants",
        "game_progress",
        "topup_requests",
        "logs",
        "referral_rewards",
        "referrals",
        "promocode_redemptions",
        "withdrawals",
        "payments",
        "purchases",
        "products",
        "servers",
        "user_achievements",
        "achievements",
        "promocodes",
        "admin_requests",
        "admins",
        "users",
    ]
    for t in drop_order:
        op.execute(sa.text(f'DROP TABLE IF EXISTS "{t}" CASCADE'))
