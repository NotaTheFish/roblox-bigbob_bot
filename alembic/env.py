import sys
import os
from logging.config import fileConfig

from sqlalchemy import create_engine
from alembic import context

# --- добавляем путь проекта (чтобы можно было импортировать backend, bot, db) ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# --- alembic config ---
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ✅ Импорт настроек и моделей
from backend.config import settings
from backend.models import Base as BackendBase
from bot.db import Base as BotBase  # если у тебя там есть Base

# ✅ Объединяем metadata
target_metadata = [BackendBase.metadata, BotBase.metadata]


# -----------------------------------------------------------------------
# OFFLINE (генерация SQL без подключения к БД)
# -----------------------------------------------------------------------
def run_migrations_offline() -> None:
    url = settings.DATABASE_URL_SYNC  # <── СИНХРОННЫЙ URL!
    context.configure(
        url=url,
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
    connectable = create_engine(settings.DATABASE_URL_SYNC)  # <── СИНХРОННЫЙ engine

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
