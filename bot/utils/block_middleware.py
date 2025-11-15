from contextlib import suppress
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove, TelegramObject
from sqlalchemy import select

from bot.db import async_session, User
from bot.keyboards.ban_appeal import BAN_APPEAL_CALLBACK, ban_appeal_keyboard
from bot.texts.block import (
    BAN_NOTIFICATION_TEXT,
    KEYBOARD_REMOVE_NOTIFICATION_TEXT,
)
from bot.states.user_states import BanAppealState


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
            if await self._is_ban_appeal_flow(event, data):
                return await handler(event, data)

            reply_markup = ban_appeal_keyboard()

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
        user_id = event.from_user.id if event.from_user else None
        await self._remove_reply_keyboard(event.message, bot, user_id)

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
        await self._remove_reply_keyboard(event)

        with suppress(Exception):
            await event.answer(
                BAN_NOTIFICATION_TEXT,
                reply_markup=reply_markup,
            )

    async def _remove_reply_keyboard(
        self,
        message: Message | None,
        bot=None,
        user_id: int | None = None,
    ) -> None:
        if message:
            with suppress(Exception):
                await message.answer(
                    KEYBOARD_REMOVE_NOTIFICATION_TEXT,
                    reply_markup=ReplyKeyboardRemove(),
                )
                return

        if bot and user_id:
            with suppress(Exception):
                await bot.send_message(
                    user_id,
                    KEYBOARD_REMOVE_NOTIFICATION_TEXT,
                    reply_markup=ReplyKeyboardRemove(),
                )

    async def _is_ban_appeal_flow(
        self,
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> bool:
        if isinstance(event, CallbackQuery):
            return event.data == BAN_APPEAL_CALLBACK

        if isinstance(event, Message):
            state: FSMContext | None = data.get("state")
            if not state:
                return False
            current_state = await state.get_state()
            return current_state == BanAppealState.waiting_for_message.state

        return False