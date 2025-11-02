from aiogram.dispatcher.handler import CancelHandler
from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select

from bot.db import async_session, User


class BlockMiddleware(BaseMiddleware):
    async def on_pre_process_message(self, message: Message, data: dict):
        if message.from_user is None:
            return

        async with async_session() as session:
            result = await session.execute(
                select(User).where(User.tg_id == message.from_user.id)
            )
            user = result.scalar_one_or_none()

            if user and user.is_blocked:
                try:
                    await message.answer("⛔ Вы заблокированы и не можете пользоваться ботом.")
                except Exception:
                    pass
                raise CancelHandler()

    async def on_pre_process_callback_query(self, call: CallbackQuery, data: dict):
        if call.from_user is None:
            return

        async with async_session() as session:
            result = await session.execute(
                select(User).where(User.tg_id == call.from_user.id)
            )
            user = result.scalar_one_or_none()

            if user and user.is_blocked:
                try:
                    await call.answer("⛔ Вы заблокированы", show_alert=True)
                except Exception:
                    pass
                raise CancelHandler()
