"""Middleware enforcing bot availability settings."""
from __future__ import annotations

from contextlib import suppress
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update

from bot.config import ROOT_ADMIN_ID
from bot.db import async_session
from bot.services.settings import BOT_STATUS_STOPPED, get_bot_status
from bot.texts.bot_status import BOT_STOPPED_MESSAGE

TelegramHandler = Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]]


class BotStatusMiddleware(BaseMiddleware):
    """Stop processing updates when the bot is intentionally paused."""

    async def __call__(
        self,
        handler: TelegramHandler,
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user_id = self._extract_user_id(event)
        if user_id is None:
            return await handler(event, data)

        async with async_session() as session:
            bot_status = await get_bot_status(session)

        if bot_status == BOT_STATUS_STOPPED and user_id != ROOT_ADMIN_ID:
            await self._notify_user(event, data, user_id)
            return None

        return await handler(event, data)

    def _extract_user_id(self, event: TelegramObject) -> int | None:
        if isinstance(event, Message):
            return getattr(event.from_user, "id", None)
        if isinstance(event, CallbackQuery):
            return getattr(event.from_user, "id", None)
        if isinstance(event, Update):
            if event.callback_query:
                return getattr(event.callback_query.from_user, "id", None)
            if event.message:
                return getattr(event.message.from_user, "id", None)
            if event.edited_message:
                return getattr(event.edited_message.from_user, "id", None)
        return getattr(event, "from_user", None) and getattr(event.from_user, "id", None)

    def _extract_message(self, event: TelegramObject) -> Message | None:
        if isinstance(event, Message):
            return event
        if isinstance(event, CallbackQuery):
            return event.message
        if isinstance(event, Update):
            return event.message or event.edited_message or (
                event.callback_query.message if event.callback_query else None
            )
        return getattr(event, "message", None)

    def _extract_callback(self, event: TelegramObject) -> CallbackQuery | None:
        if isinstance(event, CallbackQuery):
            return event
        if isinstance(event, Update):
            return event.callback_query
        return getattr(event, "callback_query", None)

    async def _notify_user(
        self,
        event: TelegramObject,
        data: Dict[str, Any],
        user_id: int,
    ) -> None:
        callback = self._extract_callback(event)
        message = self._extract_message(event)

        if callback:
            with suppress(Exception):
                await callback.answer(BOT_STOPPED_MESSAGE, show_alert=True)
            if callback.message:
                with suppress(Exception):
                    await callback.message.answer(BOT_STOPPED_MESSAGE)
                return

        if message:
            with suppress(Exception):
                await message.answer(BOT_STOPPED_MESSAGE)
            return

        bot = data.get("bot") or getattr(event, "bot", None)
        if bot:
            with suppress(Exception):
                await bot.send_message(user_id, BOT_STOPPED_MESSAGE)


__all__ = ["BotStatusMiddleware"]