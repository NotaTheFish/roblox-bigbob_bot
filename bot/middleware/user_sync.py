"""Middleware that keeps Telegram usernames in sync."""
from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update
from sqlalchemy import select

from bot.constants.users import DEFAULT_TG_USERNAME
from bot.db import User, async_session

TelegramHandler = Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]]


def normalize_tg_username(username: str | None) -> str:
    """Return a normalized Telegram username without the leading @."""

    value = (username or "").strip()
    return value or DEFAULT_TG_USERNAME


class UserSyncMiddleware(BaseMiddleware):
    """Ensure stored usernames match the latest Telegram metadata."""

    async def __call__(
        self,
        handler: TelegramHandler,
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        from_user = self._extract_from_user(event)
        if not from_user:
            return await handler(event, data)

        normalized_username = normalize_tg_username(from_user.username)
        data.setdefault("normalized_tg_username", normalized_username)

        async with async_session() as session:
            user = await session.scalar(select(User).where(User.tg_id == from_user.id))
            if not user:
                return await handler(event, data)

            if user.tg_username != normalized_username:
                user.tg_username = normalized_username
                await session.commit()
            if "current_user" not in data:
                data["current_user"] = user

        return await handler(event, data)

    def _extract_from_user(self, event: TelegramObject):
        if isinstance(event, Message):
            return event.from_user
        if isinstance(event, CallbackQuery):
            return event.from_user
        if isinstance(event, Update):
            if event.callback_query:
                return event.callback_query.from_user
            if event.message:
                return event.message.from_user
            if event.edited_message:
                return event.edited_message.from_user
        return getattr(event, "from_user", None)


__all__ = ["normalize_tg_username", "UserSyncMiddleware"]