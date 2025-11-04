from logging.config import fileConfig
import asyncio
import os

from alembic import context
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import Connection, make_url
from sqlalchemy.ext.asyncio import create_async_engine

from bot.db import Base  # импортируем Base (модели)

from dotenv import load_dotenv
load_dotenv()

# читаем URL (Render / локалка)
DB_URL = os.getenv("DB_URL") or os.getenv("DATABASE_URL")
if not DB_URL:
    raise RuntimeError("Database URL for Alembic migrations is not configured")

config = context.config
fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Проверяем async драйвер
_ASYNC_DRIVERS = {"asyncpg", "aiosqlite"}
_url = make_url(DB_URL)
_is_async = False
if "+" in _url.drivername:
    _, driver = _url.drivername.split("+", 1)
    _is_async = driver in _ASYNC_DRIVERS


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode'."""
    context.configure(
        url=DB_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _run_sync_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    # ✅ async SQLAlchemy support
    if _is_async:
        connectable = create_async_engine(DB_URL, poolclass=pool.NullPool)

        async def _run_async() -> None:
            async with connectable.connect() as connection:
                await connection.run_sync(_run_sync_migrations)
            await connectable.dispose()

        asyncio.run(_run_async())

    # ✅ fallback to sync engine
    else:
        connectable = create_engine(DB_URL, poolclass=pool.NullPool)
        with connectable.connect() as connection:
            _run_sync_migrations(connection)
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
