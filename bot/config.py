"""Application configuration loaded from environment variables."""
from __future__ import annotations

import os
from typing import List


def _parse_int_list(value: str | None) -> List[int]:
    if not value:
        return []
    result: List[int] = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            result.append(int(item))
        except ValueError:
            raise ValueError(
                f"Cannot parse integer value from ADMINS/ADMIN_ROOT_IDS entry: {item!r}"
            ) from None
    return result


def get_env(name: str, default: str | None = None, *, required: bool = False) -> str:
    value = os.getenv(name, default)
    if required and (value is None or value == ""):
        raise RuntimeError(f"Environment variable {name} is required but not set")
    return value or ""


TOKEN = get_env("TELEGRAM_TOKEN", required=True)
ADMINS = _parse_int_list(os.getenv("ADMINS"))
DATABASE_URL = get_env("DATABASE_URL", "sqlite:///data/db.sqlite3")
SECRET_KEY = get_env("SECRET_KEY", required=True)
DOMAIN = get_env("DOMAIN", required=True)
WEBHOOK_PATH = get_env("WEBHOOK_PATH", "/webhook")
if not WEBHOOK_PATH.startswith("/"):
    WEBHOOK_PATH = f"/{WEBHOOK_PATH}"

webhook_token_suffix = TOKEN.split(":")[0] if TOKEN else ""
WEBHOOK_URL = get_env(
    "WEBHOOK_URL",
    f"{DOMAIN}{WEBHOOK_PATH}/{webhook_token_suffix}" if DOMAIN else "",
)
ADMIN_ROOT_IDS = _parse_int_list(os.getenv("ADMIN_ROOT_IDS"))
ADMIN_LOGIN_PASSWORD = get_env("ADMIN_LOGIN_PASSWORD")