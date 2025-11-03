from logging.config import fileConfig
import os
from sqlalchemy import create_engine
from sqlalchemy import pool
from alembic import context

# импортируем только Base из models
from bot.db import Base

# подгружаем переменные окружения
from dotenv import load_dotenv
load_dotenv()

# читаем URL для Alembic
DB_URL = os.getenv("DB_URL")

if not DB_URL:
    raise RuntimeError("DB_URL not found in .env")

config = context.config
fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline():
    url = DB_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = create_engine(DB_URL, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
