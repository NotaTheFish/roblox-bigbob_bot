import sys
import os
from typing import Tuple
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import make_url

# --- добавляем путь проекта (чтобы можно было импортировать backend, bot, db) ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# --- alembic config ---
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ✅ Импорт metadata и helper'ов БД
from bot.db import Base

target_metadata = Base.metadata

# --- выставляем URL для Alembic ---
def _get_database_url() -> Tuple[str, str]:
    """Return the first available DB URL and the env var it came from."""

    candidates = ("DATABASE_URL_SYNC", "DATABASE_URL", "DB_URL")
    for env_name in candidates:
        value = os.getenv(env_name)
        if value:
            return value, env_name

    raise RuntimeError(
        "Database URL not found. Set DATABASE_URL, DATABASE_URL_SYNC or DB_URL before "
        "running Alembic."
    )


database_url, _ = _get_database_url()
url = make_url(database_url)

# Alembic / psycopg2 всегда работают синхронно. Если пользователь
# передал async-драйвер (postgresql+asyncpg) или опустил драйвер, меняем его.
drivername = url.drivername
if "+" in drivername:
    dialect, driver = drivername.split("+", 1)
else:
    dialect, driver = drivername, None

if dialect == "postgresql":
    if driver in (None, "asyncpg"):
        driver = "psycopg2"
    drivername = f"{dialect}+{driver}"

sync_database_url = url.set(drivername=drivername)
config.set_main_option("sqlalchemy.url", str(sync_database_url))


# -----------------------------------------------------------------------
# OFFLINE (генерация SQL без подключения к БД)
# -----------------------------------------------------------------------
def run_migrations_offline() -> None:
    context.configure(
        url=str(sync_database_url),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# -----------------------------------------------------------------------
# ONLINE (нормальные миграции)
# -----------------------------------------------------------------------
def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
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
