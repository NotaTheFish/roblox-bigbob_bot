from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.exceptions import SkipHandler
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy import select

from bot.db import async_session, User


class BlockMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user_id: int | None = None

        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id

        if user_id is None:
            return await handler(event, data)

        async with async_session() as session:
            result = await session.execute(
                select(User).where(User.tg_id == user_id)
            )
            user = result.scalar_one_or_none()

        if user and user.is_blocked:
            try:
                if isinstance(event, CallbackQuery):
                    await event.answer("⛔ Вы заблокированы", show_alert=True)
                elif isinstance(event, Message):
                    await event.answer("⛔ Вы заблокированы и не можете пользоваться ботом.")
            except Exception:
                pass
            raise SkipHandler()

        return await handler(event, data)
