"""Helpers for interacting with the Telegram Bot API."""
from __future__ import annotations

from typing import Any, Dict

import httpx

from ..config import get_settings
from ..logging import get_logger

logger = get_logger(__name__)


class TelegramNotificationError(RuntimeError):
    """Raised when sending a Telegram notification fails."""


async def send_message(
    chat_id: int,
    text: str,
    *,
    parse_mode: str | None = None,
    disable_web_page_preview: bool = True,
) -> None:
    """Send a message via the Telegram Bot API."""

    token = get_settings().telegram_bot_token
    if not token:
        logger.debug(
            "Telegram bot token missing, skipping notification",
            extra={"chat_id": chat_id},
        )
        return

    if not chat_id:
        logger.debug("Empty chat_id provided, skipping notification")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": disable_web_page_preview,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:  # pragma: no cover - network issues
        status_code = exc.response.status_code if exc.response else None
        if status_code == 403:
            logger.warning(
                "Telegram API request forbidden",
                extra={"chat_id": chat_id},
                exc_info=True,
            )
            return

        logger.warning(
            "Telegram API request failed",
            extra={"chat_id": chat_id},
            exc_info=True,
        )
        raise TelegramNotificationError("Telegram API request failed") from exc
    except httpx.HTTPError as exc:  # pragma: no cover - network issues
        logger.warning(
            "Telegram API request failed",
            extra={"chat_id": chat_id},
            exc_info=True,
        )
        raise TelegramNotificationError("Telegram API request failed") from exc

    data = response.json()
    if not data.get("ok"):
        logger.warning(
            "Telegram API returned error", extra={"chat_id": chat_id, "response": data}
        )
        raise TelegramNotificationError(
            f"Telegram API returned error: {data.get('description', 'unknown error')}"
        )


__all__ = ["TelegramNotificationError", "send_message"]