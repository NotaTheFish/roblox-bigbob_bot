import sys
import os
from logging.config import fileConfig

from alembic import context

# --- добавляем путь проекта (чтобы можно было импортировать backend, bot, db) ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# --- alembic config ---
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ✅ Импорт metadata и helper'ов БД
from bot.db import Base, get_sync_database_url
from sqlalchemy.engine.url import make_url

sync_url = get_sync_database_url()
sync_url_obj = make_url(sync_url)
sync_connect_args = {"sslmode": "require"} if sync_url_obj.get_backend_name() == "postgresql" else {}

target_metadata = Base.metadata

# --- выставляем URL для Alembic ---
config.set_main_option("sqlalchemy.url", sync_url)


# -----------------------------------------------------------------------
# OFFLINE (генерация SQL без подключения к БД)
# -----------------------------------------------------------------------
def run_migrations_offline() -> None:
    context.configure(
        url=sync_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# -----------------------------------------------------------------------
# ONLINE (нормальные миграции)
# -----------------------------------------------------------------------
from sqlalchemy import create_engine


def run_migrations_online() -> None:
    connectable = create_engine(sync_url, connect_args=sync_connect_args)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


# -----------------------------------------------------------------------
# ENTRY POINT
# -----------------------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
