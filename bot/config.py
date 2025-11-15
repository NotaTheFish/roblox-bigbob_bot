import os
from decimal import Decimal, InvalidOperation
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


def _get_decimal_env(name: str, default: str) -> Decimal:
    raw_value = get_env(name, default)
    try:
        return Decimal(raw_value)
    except InvalidOperation as exc:  # pragma: no cover - configuration error
        raise RuntimeError(f"Environment variable {name} must be a decimal number") from exc


# === SETTINGS (для Alembic и DB) =====================================
class Settings(BaseSettings):
    DATABASE_URL: str

    class Config:
        env_file = ".env"
        extra = "ignore"  # ✅ игнорировать остальные переменные в .env

settings = Settings()


# === БОТ ==============================================================
TOKEN = get_env("TELEGRAM_TOKEN", required=True)

ROOT_ADMIN_ID = int(get_env("ROOT_ADMIN_ID", "0"))

DATABASE_URL = settings.DATABASE_URL

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

WALLET_PAY_API_BASE = get_env("WALLET_PAY_API_BASE", "https://pay.wallet.tg")
WALLET_PAY_API_KEY = get_env("WALLET_PAY_API_KEY", "")
WALLET_PAY_SHOP_ID = get_env("WALLET_PAY_SHOP_ID", "")

TON_PAYMENT_MARKUP_PERCENT = _get_decimal_env("TON_PAYMENT_MARKUP_PERCENT", "0")
TON_INVOICE_TTL_SECONDS = int(get_env("TON_INVOICE_TTL_SECONDS", "900"))
