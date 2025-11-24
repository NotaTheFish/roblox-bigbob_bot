from aiogram import BaseMiddleware
from aiogram.types import Message
from typing import Callable, Awaitable, Dict, Any

# Список всех типов контента, которые считаются вложениями
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
        event: Message,
        data: Dict[str, Any]
    ) -> Any:

        # Если тип контента — вложение, блокируем
        if event.content_type in BLOCKED_CONTENT_TYPES:
            try:
                await event.answer(
                    "⚠️ Отправка файлов и вложений запрещена в целях безопасности."
                )
            except:
                pass

            return  # Ничего не передаём дальше

        return await handler(event, data)