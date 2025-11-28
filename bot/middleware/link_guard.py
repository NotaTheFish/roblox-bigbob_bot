"""Middleware that blocks user-supplied links and homograph URLs."""
from __future__ import annotations

import logging
import re
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.config import ADMIN_ROOT_IDS, ADMINS, ROOT_ADMIN_ID
from bot.db import LogEntry, async_session

TelegramHandler = Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]]

logger = logging.getLogger(__name__)

URL_PATTERN = re.compile(
    r"(?i)\b((?:https?://|www\.)\S+|(?:[a-z0-9-]+\.)+(?:[a-z]{2,}|xn--)\S*)"
)
CYRILLIC = re.compile("[\u0400-\u04FF]")
LATIN = re.compile("[A-Za-z]")

ADMIN_ALLOWLIST_COMMANDS = ("/admin_login", "/admin", "/admin_menu", "/admin_open")
ADMIN_ALLOWLIST_CALLBACK_PREFIXES = (
    "admin",
    "admin_",
    "admin-menu",
    "admin-panel",
    "confirm_block_admin",
    "cancel_block_admin",
    "demote_admin",
)


class LinkGuardMiddleware(BaseMiddleware):
    """Block clickable URLs/homographs and log the attempt."""

    def __init__(self) -> None:
        super().__init__()

    async def __call__(
        self, handler: TelegramHandler, event: TelegramObject, data: Dict[str, Any]
    ) -> Any:
        text = self._extract_text(event)
        user_id = self._get_user_id(event)

        if self._is_trusted_admin(user_id, data):
            return await handler(event, data)

        if self._is_allowlisted_payload(text):
            return await handler(event, data)

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
    def _contains_link(text: str, *, allow_mixed_script: bool = True) -> bool:
        return bool(
            URL_PATTERN.search(text)
            or ("xn--" in text.lower())
            or (allow_mixed_script and CYRILLIC.search(text) and LATIN.search(text))
        )

    @staticmethod
    def _get_user_id(event: TelegramObject) -> int | None:
        if isinstance(event, Message) and event.from_user:
            return event.from_user.id
        if isinstance(event, CallbackQuery) and event.from_user:
            return event.from_user.id
        return None

    @staticmethod
    def _is_allowlisted_payload(text: str) -> bool:
        if not text:
            return False

        lowered = text.lower()

        if any(lowered.startswith(cmd) for cmd in ADMIN_ALLOWLIST_COMMANDS):
            return True

        return any(lowered.startswith(prefix) for prefix in ADMIN_ALLOWLIST_CALLBACK_PREFIXES)

    @staticmethod
    def _is_trusted_admin(user_id: int | None, data: Dict[str, Any]) -> bool:
        if user_id is None:
            return False

        trusted_ids = {ROOT_ADMIN_ID, *(ADMINS or []), *(ADMIN_ROOT_IDS or [])}

        if user_id in trusted_ids:
            return True

        if isinstance(data.get("is_admin"), bool) and data["is_admin"]:
            return True

        current_user = data.get("current_user")
        if current_user:
            if getattr(current_user, "telegram_id", None) == user_id and getattr(
                current_user, "is_root", False
            ):
                return True

            if getattr(current_user, "tg_id", None) == user_id and getattr(
                current_user, "is_root", False
            ):
                return True

        return False

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