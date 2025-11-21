from __future__ import annotations

from functools import lru_cache

from bot.config import DATABASE_URL, get_env


class Settings:
    """Application settings resolved from environment variables."""

    database_url: str = DATABASE_URL
    hmac_secret: str
    idempotency_ttl_seconds: int
    achievements_recalc_interval_seconds: int
    roblox_api_base_url: str
    telegram_payment_secret: str
    telegram_bot_token: str

    def __init__(self) -> None:
        self.hmac_secret = get_env("BACKEND_HMAC_SECRET", required=True)
        self.idempotency_ttl_seconds = int(get_env("BACKEND_IDEMPOTENCY_TTL", "3600"))
        self.achievements_recalc_interval_seconds = int(
            get_env("BACKEND_ACHIEVEMENTS_RECALC_INTERVAL", "300")
        )
        self.roblox_api_base_url = get_env("ROBLOX_API_BASE_URL", "")
        self.telegram_payment_secret = get_env("TELEGRAM_PAYMENT_SECRET", "")
        self.telegram_bot_token = get_env("TELEGRAM_TOKEN", "")


@lru_cache()
def get_settings() -> Settings:
    return Settings()