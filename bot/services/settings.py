"""Helpers for interacting with dynamic application settings."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import Setting

TON_RATE_SETTING_KEY = "ton_to_nuts_rate"
BOT_STATUS_SETTING_KEY = "bot_status"
BOT_STATUS_RUNNING = "running"
BOT_STATUS_STOPPED = "stopped"
DEFAULT_BOT_STATUS = BOT_STATUS_RUNNING


async def get_setting(session: AsyncSession, key: str) -> Setting | None:
    """Return the stored setting row for the given key if it exists."""

    return await session.scalar(select(Setting).where(Setting.key == key))


async def upsert_setting(
    session: AsyncSession,
    *,
    key: str,
    value: Any,
    description: str | None = None,
) -> Setting:
    """Create or update a setting entry with the supplied value."""

    setting = await get_setting(session, key)
    payload: Any
    if isinstance(value, Mapping):
        payload = dict(value)
    else:
        payload = {"value": value}

    if setting:
        setting.value = payload
        if description is not None:
            setting.description = description
    else:
        setting = Setting(key=key, value=payload, description=description)
        session.add(setting)

    await session.flush()
    return setting


def _extract_decimal(value: Any) -> Decimal:
    if isinstance(value, Mapping) and "value" in value:
        value = value["value"]
    if value is None:
        raise ValueError("Setting does not contain a numeric value")
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:  # pragma: no cover - defensive
        raise ValueError("Cannot parse numeric setting value") from exc


def _extract_bot_status(value: Any) -> str:
    if isinstance(value, Mapping) and "value" in value:
        value = value["value"]
    if isinstance(value, str):
        normalized = value.lower()
        if normalized in {BOT_STATUS_RUNNING, BOT_STATUS_STOPPED}:
            return normalized
    return DEFAULT_BOT_STATUS


async def get_bot_status(session: AsyncSession) -> str:
    """Return the current bot status or the default when unset."""

    setting = await get_setting(session, BOT_STATUS_SETTING_KEY)
    if not setting or setting.value is None:
        return DEFAULT_BOT_STATUS
    return _extract_bot_status(setting.value)


async def get_ton_rate(session: AsyncSession) -> Decimal | None:
    """Return the TON→nuts exchange rate or ``None`` when unavailable."""

    setting = await get_setting(session, TON_RATE_SETTING_KEY)
    if not setting or setting.value is None:
        return None
    try:
        return _extract_decimal(setting.value)
    except ValueError:
        return None


async def set_ton_rate(
    session: AsyncSession,
    *,
    rate: Decimal | float | str,
    description: str | None = None,
) -> Setting:
    """Persist the TON→nuts exchange rate for future conversions."""

    value = Decimal(str(rate))
    return await upsert_setting(
        session,
        key=TON_RATE_SETTING_KEY,
        value={"value": str(value)},
        description=description,
    )


async def set_bot_status(
    session: AsyncSession,
    *,
    status: str,
    description: str | None = None,
) -> Setting:
    """Persist the bot availability status."""

    normalized = status.lower()
    if normalized not in {BOT_STATUS_RUNNING, BOT_STATUS_STOPPED}:
        raise ValueError("Unsupported bot status")
    return await upsert_setting(
        session,
        key=BOT_STATUS_SETTING_KEY,
        value={"value": normalized},
        description=description,
    )


__all__ = [
    "BOT_STATUS_SETTING_KEY",
    "BOT_STATUS_RUNNING",
    "BOT_STATUS_STOPPED",
    "DEFAULT_BOT_STATUS",
    "get_bot_status",
    "set_bot_status",
    "TON_RATE_SETTING_KEY",
    "get_setting",
    "get_ton_rate",
    "set_ton_rate",
    "upsert_setting",
]