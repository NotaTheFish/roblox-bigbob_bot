"""Middleware preventing redundant callback message edits."""
from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, TelegramObject

TelegramHandler = Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]]


_NOT_PROVIDED = object()


def _normalize_markup(markup: InlineKeyboardMarkup | None) -> Any:
    if markup is None:
        return None
    if hasattr(markup, "model_dump"):
        return markup.model_dump(exclude_none=True)
    return markup


class CallbackMessageProxy:
    """Proxy that deduplicates identical edits on a callback message."""

    def __init__(self, callback: CallbackQuery, *, hint: str | None) -> None:
        self._callback = callback
        self._message = callback.message
        self._hint = hint
        self._text_cache = getattr(self._message, "text", None)
        self._markup_cache = getattr(self._message, "reply_markup", None)

    def __getattr__(self, name: str):
        if name == "text":
            return self._text_cache
        if name == "reply_markup":
            return self._markup_cache
        return getattr(self._message, name)

    def _current_text(self) -> str | None:
        return self._text_cache

    def _target_markup(self, provided: InlineKeyboardMarkup | object) -> InlineKeyboardMarkup | None:
        if provided is _NOT_PROVIDED:
            return self._markup_cache
        return provided

    def _markups_equal(self, new_markup: InlineKeyboardMarkup | None) -> bool:
        return _normalize_markup(self._markup_cache) == _normalize_markup(new_markup)

    async def _answer_only(self):
        if self._hint is None:
            return await self._callback.answer()
        return await self._callback.answer(self._hint)

    def _remember_state(
        self,
        *,
        text: str | None = None,
        markup: InlineKeyboardMarkup | object = _NOT_PROVIDED,
    ) -> None:
        if text is not None:
            self._text_cache = text
        if markup is not _NOT_PROVIDED:
            self._markup_cache = markup

    async def edit_text(self, text: str, **kwargs):
        markup_provided = kwargs.get("reply_markup", _NOT_PROVIDED)
        target_markup = self._target_markup(markup_provided)

        if text == self._current_text() and self._markups_equal(target_markup):
            return await self._answer_only()

        result = await self._message.edit_text(text, **kwargs)
        self._remember_state(text=text, markup=target_markup if markup_provided is not _NOT_PROVIDED else _NOT_PROVIDED)
        return result

    async def edit_reply_markup(self, reply_markup: InlineKeyboardMarkup | None = None, **kwargs):
        if self._markups_equal(reply_markup):
            return await self._answer_only()

        result = await self._message.edit_reply_markup(reply_markup=reply_markup, **kwargs)
        self._remember_state(markup=reply_markup)
        return result

    async def edit_text_and_reply_markup(
        self, text: str, reply_markup: InlineKeyboardMarkup | None = None, **kwargs
    ):
        kwargs["reply_markup"] = reply_markup
        return await self.edit_text(text, **kwargs)


class CallbackDedupMiddleware(BaseMiddleware):
    """Wrap callback messages to avoid MessageNotModified errors on repeat presses."""

    def __init__(self, *, hint: str | None = "Сообщение уже актуально") -> None:
        super().__init__()
        self._hint = hint

    async def __call__(
        self,
        handler: TelegramHandler,
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if not isinstance(event, CallbackQuery) or event.message is None:
            return await handler(event, data)

        if self._should_skip(event):
            return await handler(event, data)

        proxy = CallbackMessageProxy(event, hint=self._hint)
        object.__setattr__(event, "message", proxy)
        data["event_message"] = proxy
        return await handler(event, data)

    def _should_skip(self, event: CallbackQuery) -> bool:
        data = event.data or ""
        message = event.message
        if data.startswith("logs:"):
            return True
        if getattr(message, "is_topic_message", False):
            return True
        if getattr(message, "via_bot", None) is not None:
            return True
        return False


__all__ = ["CallbackDedupMiddleware"]