import sys
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

# --- добавляем путь проекта (чтобы можно было импортировать backend, bot, db) ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# --- alembic config ---
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ✅ Импорт metadata и helper'ов БД
from bot.db import Base

target_metadata = Base.metadata

def get_sync_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set. Configure it before running Alembic.")

    return database_url.replace("+asyncpg", "")


# -----------------------------------------------------------------------
# OFFLINE (генерация SQL без подключения к БД)
# -----------------------------------------------------------------------
def run_migrations_offline() -> None:
    context.configure(
        url=get_sync_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# -----------------------------------------------------------------------
# ONLINE (нормальные миграции)
# -----------------------------------------------------------------------
def _build_connect_args(url: str) -> dict:
    """Return connection arguments suitable for the provided database URL."""

    if url.startswith("postgresql"):
        sslmode = os.getenv("DATABASE_SSLMODE", "require")
        return {"sslmode": sslmode}

    return {}


def run_migrations_online() -> None:
    sync_url = get_sync_url()
    connectable = create_engine(
        sync_url,
        poolclass=pool.NullPool,
        connect_args=_build_connect_args(sync_url),
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


# Alembic entrypoint
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
