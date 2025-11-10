import os
from typing import List
from dotenv import load_dotenv
from pydantic_settings import BaseSettings  # <-- исправленный импорт

# Загружаем .env
load_dotenv()


def _parse_int_list(value: str | None) -> List[int]:
    if not value:
        return []
    result = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            result.append(int(item))
        except ValueError:
            raise ValueError(
                f"Cannot parse integer value from ADMINS/ADMIN_ROOT_IDS entry: {item!r}"
            )
    return result


def get_env(name: str, default: str | None = None, *, required: bool = False) -> str:
    value = os.getenv(name, default)
    if required and (value is None or value == ""):
        raise RuntimeError(f"Environment variable {name} is required but not set")
    return value or ""


# === SETTINGS (для Alembic и DB) =====================================
class Settings(BaseSettings):
    DATABASE_URL: str
    DATABASE_URL_SYNC: str | None = None

    class Config:
        env_file = ".env"
        extra = "ignore"  # ✅ игнорировать остальные переменные в .env



settings = Settings()


def _derive_sync_database_url(async_url: str) -> str:
    async_prefix = "postgresql+asyncpg://"
    sync_prefix = "postgresql+psycopg2://"
    if async_url.startswith(async_prefix):
        return sync_prefix + async_url[len(async_prefix) :]
    return async_url


if settings.DATABASE_URL_SYNC is None:
    fallback_sync_url = _derive_sync_database_url(settings.DATABASE_URL)
    settings = settings.model_copy(update={"DATABASE_URL_SYNC": fallback_sync_url})


# === БОТ ==============================================================
TOKEN = get_env("TELEGRAM_TOKEN", required=True)

ROOT_ADMIN_ID = int(get_env("ROOT_ADMIN_ID", "0"))

DATABASE_URL = settings.DATABASE_URL
DATABASE_URL_SYNC = settings.DATABASE_URL_SYNC

DOMAIN = get_env("DOMAIN", "")
WEBHOOK_PATH = get_env("WEBHOOK_PATH", "/webhook")
if not WEBHOOK_PATH.startswith("/"):
    WEBHOOK_PATH = f"/{WEBHOOK_PATH}"

webhook_token_suffix = TOKEN.split(":")[0]
WEBHOOK_URL = get_env(
    "WEBHOOK_URL",
    f"{DOMAIN}{WEBHOOK_PATH}/{webhook_token_suffix}" if DOMAIN else "",
)

WEBAPP_HOST = "0.0.0.0"
WEBAPP_PORT = int(os.getenv("PORT", "10000"))

ADMIN_LOGIN_PASSWORD = get_env("ADMIN_LOGIN_PASSWORD", required=True)

ADMINS = _parse_int_list(os.getenv("ADMINS"))
ADMIN_ROOT_IDS = _parse_int_list(os.getenv("ADMIN_ROOT_IDS"))
