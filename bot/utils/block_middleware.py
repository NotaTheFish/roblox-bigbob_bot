from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from bot.db import SessionLocal, User


class BlockMiddleware(BaseMiddleware):
    async def on_pre_process_message(self, message: Message, data: dict):
        with SessionLocal() as s:
            user = s.query(User).filter_by(tg_id=message.from_user.id).first()
            if user and user.is_blocked:
                try:
                    await message.answer("⛔ Вы заблокированы и не можете пользоваться ботом.")
                except:
                    pass
                raise StopIteration  # отмена обработки

    async def on_pre_process_callback_query(self, call: CallbackQuery, data: dict):
        with SessionLocal() as s:
            user = s.query(User).filter_by(tg_id=call.from_user.id).first()
            if user and user.is_blocked:
                try:
                    await call.answer("⛔ Вы заблокированы", show_alert=True)
                except:
                    pass
                raise StopIteration  # отмена обработки
