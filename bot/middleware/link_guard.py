"""Middleware that blocks user-supplied links and homograph URLs."""
from __future__ import annotations

import logging
import re
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.db import LogEntry, async_session

TelegramHandler = Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]]

logger = logging.getLogger(__name__)

URL_PATTERN = re.compile(
    r"(?i)\b((?:https?://|www\.)\S+|(?:[a-z0-9-]+\.)+(?:[a-z]{2,}|xn--)\S*)"
)
CYRILLIC = re.compile("[\u0400-\u04FF]")
LATIN = re.compile("[A-Za-z]")


class LinkGuardMiddleware(BaseMiddleware):
    """Block clickable URLs/homographs and log the attempt."""

    def __init__(self) -> None:
        super().__init__()

    async def __call__(
        self, handler: TelegramHandler, event: TelegramObject, data: Dict[str, Any]
    ) -> Any:
        text = self._extract_text(event)

        if text and self._contains_link(text):
            await self._neutralize(event)
            await self._log_security_event(event, text)
            return None

        return await handler(event, data)

    @staticmethod
    def _extract_text(event: TelegramObject) -> str:
        if isinstance(event, Message):
            return (event.text or event.caption or "").strip()
        if isinstance(event, CallbackQuery):
            payload = (event.data or "").strip()
            if payload:
                return payload
            if event.message:
                return (event.message.text or event.message.caption or "").strip()
        return ""

    @staticmethod
    def _contains_link(text: str) -> bool:
        return bool(
            URL_PATTERN.search(text)
            or ("xn--" in text.lower())
            or (CYRILLIC.search(text) and LATIN.search(text))
        )

    @staticmethod
    def _get_user_id(event: TelegramObject) -> int | None:
        if isinstance(event, Message) and event.from_user:
            return event.from_user.id
        if isinstance(event, CallbackQuery) and event.from_user:
            return event.from_user.id
        return None

    async def _neutralize(self, event: TelegramObject) -> None:
        try:
            if isinstance(event, Message):
                await event.answer(
                    "🚫 Ссылки в сообщениях запрещены.",
                    disable_web_page_preview=True,
                    parse_mode=None,
                )
            elif isinstance(event, CallbackQuery):
                await event.answer("🚫 Ссылки запрещены.", show_alert=True)
                if event.message:
                    await event.message.edit_text(
                        "🚫 Ссылки запрещены.",
                        disable_web_page_preview=True,
                        parse_mode=None,
                    )
        except Exception:
            logger.debug("Failed to send link guard notification", exc_info=True)

    async def _log_security_event(self, event: TelegramObject, text: str) -> None:
        user_id = self._get_user_id(event)

        try:
            async with async_session() as session:
                session.add(
                    LogEntry(
                        telegram_id=user_id,
                        event_type="security.link_blocked",
                        message="Blocked potential link or homograph payload",
                        data={"text_sample": text[:256]},
                    )
                )
                await session.commit()
        except Exception:
            logger.debug("Failed to log link block event", exc_info=True)