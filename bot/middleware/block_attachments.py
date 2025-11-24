from aiogram import BaseMiddleware
from aiogram.types import Message
from typing import Callable, Awaitable, Dict, Any


BLOCKED_CONTENT_TYPES = {
    "photo",
    "video",
    "animation",
    "audio",
    "document",
    "voice",
    "video_note",
    "contact",
    "location",
    "venue",
    "sticker",
}


class BlockAttachmentsMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any]
    ) -> Any:

        # Обрабатываем только сообщения
        if isinstance(event, Message):

            if event.content_type in BLOCKED_CONTENT_TYPES:
                try:
                    await event.answer(
                        "⚠️ Отправка файлов, фото и вложений запрещена."
                    )
                except:
                    pass

                return  # Отменяем дальнейшую обработку

        # Для всех остальных типов (CallbackQuery и т.д.)
        return await handler(event, data)
