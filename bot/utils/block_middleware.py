from contextlib import suppress
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy import select

from bot.db import async_session, User
from bot.keyboards.ban_appeal import ban_appeal_keyboard
from bot.texts.block import BAN_NOTIFICATION_TEXT


class BlockMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user_id: int | None = None

        # Check event type and get user ID
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

        # ❌ If blocked — send message and stop here
        if user and user.is_blocked:
            reply_markup = ban_appeal_keyboard() if user.ban_appeal_at is None else None

            if isinstance(event, CallbackQuery):
                bot = data.get("bot") or getattr(event, "bot", None)
                await self._handle_blocked_callback(event, reply_markup, bot)
            elif isinstance(event, Message):
                await self._handle_blocked_message(event, reply_markup)

            return  # ⬅️ ключевой момент — просто завершаем middleware

        # ✅ Continue processing
        return await handler(event, data)

    async def _handle_blocked_callback(
        self,
        event: CallbackQuery,
        reply_markup,
        bot,
    ) -> None:
        if event.message:
            try:
                await event.message.edit_text(
                    BAN_NOTIFICATION_TEXT,
                    reply_markup=reply_markup,
                )
            except TelegramBadRequest:
                with suppress(Exception):
                    await event.message.answer(
                        BAN_NOTIFICATION_TEXT,
                        reply_markup=reply_markup,
                    )
            except Exception:
                with suppress(Exception):
                    await event.message.answer(
                        BAN_NOTIFICATION_TEXT,
                        reply_markup=reply_markup,
                    )
        elif bot and event.from_user:
            with suppress(Exception):
                await bot.send_message(
                    event.from_user.id,
                    BAN_NOTIFICATION_TEXT,
                    reply_markup=reply_markup,
                )

        with suppress(Exception):
            await event.answer()

    async def _handle_blocked_message(self, event: Message, reply_markup) -> None:
        with suppress(Exception):
            await event.answer(
                BAN_NOTIFICATION_TEXT,
                reply_markup=reply_markup,
            )
