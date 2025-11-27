import datetime

import pytest
from aiogram.types import Chat, ChatJoinRequest, Message, Update, User

from bot.middleware.event_type_injector import EventTypeInjectorMiddleware


def _build_user(user_id: int = 1) -> User:
    return User.model_construct(id=user_id, is_bot=False, first_name="Tester")


def _build_chat(chat_id: int = 1) -> Chat:
    return Chat.model_construct(id=chat_id, type="private")


@pytest.mark.anyio
async def test_injects_event_type_for_message():
    middleware = EventTypeInjectorMiddleware()
    message = Message.model_construct(
        message_id=1,
        date=datetime.datetime.now(),
        chat=_build_chat(),
        text="hi",
        from_user=_build_user(),
    )

    captured: dict[str, str | None] = {}

    async def handler(event, data):
        captured["event_type"] = data.get("event_type")
        return "handled"

    result = await middleware(handler, message, {})

    assert result == "handled"
    assert captured["event_type"] == "message"


@pytest.mark.anyio
async def test_preserves_existing_event_type():
    middleware = EventTypeInjectorMiddleware()
    message = Message.model_construct(
        message_id=1,
        date=datetime.datetime.now(),
        chat=_build_chat(),
        text="hi",
        from_user=_build_user(),
    )

    captured: dict[str, str | None] = {}

    async def handler(event, data):
        captured["event_type"] = data.get("event_type")
        return "handled"

    result = await middleware(handler, message, {"event_type": "custom"})

    assert result == "handled"
    assert captured["event_type"] == "custom"


@pytest.mark.anyio
async def test_update_with_join_request_detected():
    middleware = EventTypeInjectorMiddleware()
    join_request = ChatJoinRequest.model_construct(
        chat=_build_chat(10),
        from_user=_build_user(99),
        date=datetime.datetime.now(),
    )
    update = Update.model_construct(update_id=42, chat_join_request=join_request)

    captured: dict[str, str | None] = {}

    async def handler(event, data):
        captured["event_type"] = data.get("event_type")
        return "handled"

    result = await middleware(handler, update, {})

    assert result == "handled"
    assert captured["event_type"] == "chat_join_request"


@pytest.mark.anyio
async def test_unknown_event_type_fallback():
    middleware = EventTypeInjectorMiddleware()

    captured: dict[str, str | None] = {}

    async def handler(event, data):
        captured["event_type"] = data.get("event_type")
        return "handled"

    result = await middleware(handler, object(), {})

    assert result == "handled"
    assert captured["event_type"] == "unknown"