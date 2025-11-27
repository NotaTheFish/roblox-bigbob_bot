"""Middleware to inject a best-effort event_type into handler data."""
from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import (
    CallbackQuery,
    ChatJoinRequest,
    ChatMemberUpdated,
    ChosenInlineResult,
    InlineQuery,
    Message,
    Poll,
    PollAnswer,
    PreCheckoutQuery,
    ShippingQuery,
    TelegramObject,
    Update,
)

TelegramHandler = Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]]


class EventTypeInjectorMiddleware(BaseMiddleware):
    """Ensure handlers receive a populated ``event_type`` value."""

    async def __call__(
        self,
        handler: TelegramHandler,
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if data.get("event_type") is None:
            data["event_type"] = self._detect_event_type(event)

        return await handler(event, data)

    def _detect_event_type(self, event: TelegramObject) -> str:
        if isinstance(event, Message):
            return "message"
        if isinstance(event, CallbackQuery):
            return "callback_query"
        if isinstance(event, InlineQuery):
            return "inline_query"
        if isinstance(event, ChosenInlineResult):
            return "chosen_inline_result"
        if isinstance(event, ShippingQuery):
            return "shipping_query"
        if isinstance(event, PreCheckoutQuery):
            return "pre_checkout_query"
        if isinstance(event, Poll):
            return "poll"
        if isinstance(event, PollAnswer):
            return "poll_answer"
        if isinstance(event, ChatJoinRequest):
            return "chat_join_request"
        if isinstance(event, ChatMemberUpdated):
            return "chat_member_updated"

        if isinstance(event, Update):
            if event.message:
                return "message"
            if event.edited_message:
                return "edited_message"
            if event.callback_query:
                return "callback_query"
            if event.inline_query:
                return "inline_query"
            if event.chosen_inline_result:
                return "chosen_inline_result"
            if event.shipping_query:
                return "shipping_query"
            if event.pre_checkout_query:
                return "pre_checkout_query"
            if event.poll:
                return "poll"
            if event.poll_answer:
                return "poll_answer"
            if event.chat_join_request:
                return "chat_join_request"
            if event.chat_member:
                return "chat_member_updated"
            if event.my_chat_member:
                return "chat_member_updated"

        return "unknown"


__all__ = ["EventTypeInjectorMiddleware"]