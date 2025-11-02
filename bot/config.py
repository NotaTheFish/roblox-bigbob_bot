import os
from typing import List


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


# ✅ Основной токен Telegram бота
TOKEN = get_env("TELEGRAM_TOKEN", required=True)

# ✅ Главный админ
ROOT_ADMIN_ID = int(get_env("ROOT_ADMIN_ID", "0"))

# ✅ База данных
DATABASE_URL = get_env(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres",
)

# ✅ Webhook настройки
DOMAIN = get_env("DOMAIN", "")
WEBHOOK_PATH = get_env("WEBHOOK_PATH", "/webhook")
if not WEBHOOK_PATH.startswith("/"):
    WEBHOOK_PATH = f"/{WEBHOOK_PATH}"

webhook_token_suffix = TOKEN.split(":")[0]
WEBHOOK_URL = get_env(
    "WEBHOOK_URL",
    f"{DOMAIN}{WEBHOOK_PATH}/{webhook_token_suffix}" if DOMAIN else "",
)

# ✅ Хост/порт (Render)
WEBAPP_HOST = "0.0.0.0"
WEBAPP_PORT = int(os.getenv("PORT", "10000"))

# ✅ Секрет для админ-панели
ADMIN_LOGIN_PASSWORD = get_env("ADMIN_LOGIN_PASSWORD", required=True)

# ✅ Админы
ADMINS = _parse_int_list(os.getenv("ADMINS"))
ADMIN_ROOT_IDS = _parse_int_list(os.getenv("ADMIN_ROOT_IDS"))