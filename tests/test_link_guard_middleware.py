import datetime

import pytest
from aiogram.types import CallbackQuery, Chat, Message, User

import bot.middleware.link_guard as link_guard
from bot.middleware.link_guard import LinkGuardMiddleware
from db.models import LogEntry
from tests.conftest import FakeAsyncSession, make_async_session_stub


def _build_message(text: str, user_id: int = 10) -> Message:
    message = Message.model_construct(
        message_id=1,
        date=datetime.datetime.now(),
        chat=Chat.model_construct(id=1, type="private"),
        text=text,
        from_user=User.model_construct(id=user_id, is_bot=False, first_name="Tester"),
    )
    object.__setattr__(message, "answers", [])

    async def answer(text: str, **kwargs):
        message.answers.append((text, kwargs))
        return text

    object.__setattr__(message, "answer", answer)
    return message


def _build_callback(payload: str, user_id: int = 10) -> CallbackQuery:
    message = _build_message("callback host")

    async def edit_text(text: str, **kwargs):
        message.edits.append((text, kwargs))
        return text

    object.__setattr__(message, "edits", [])
    object.__setattr__(message, "edit_text", edit_text)

    callback = CallbackQuery.model_construct(
        id="1",
        from_user=User.model_construct(id=user_id, is_bot=False, first_name="Tester"),
        chat_instance="instance",
        data=payload,
        message=message,
    )
    object.__setattr__(callback, "answers", [])

    async def answer(text: str | None = None, show_alert: bool = False):
        callback.answers.append((text, show_alert))
        return None

    object.__setattr__(callback, "answer", answer)
    return callback


@pytest.mark.anyio
async def test_message_link_blocked_and_logged(monkeypatch):
    session = FakeAsyncSession()
    monkeypatch.setattr(link_guard, "async_session", make_async_session_stub(session))

    middleware = LinkGuardMiddleware()
    message = _build_message("check https://example.com for prizes")

    handler_called = False

    async def handler(event, data):
        nonlocal handler_called
        handler_called = True
        return "handled"

    result = await middleware(handler, message, {})

    assert result is None
    assert handler_called is False
    assert message.answers == [
        (
            "🚫 Ссылки в сообщениях запрещены.",
            {"disable_web_page_preview": True, "parse_mode": None},
        )
    ]

    log_entry = next(obj for obj in session.added if isinstance(obj, LogEntry))
    assert log_entry.event_type == "security.link_blocked"
    assert "example.com" in (log_entry.data or {}).get("text_sample", "")
    assert session.committed is True


@pytest.mark.anyio
async def test_callback_homograph_blocked_without_http(monkeypatch):
    session = FakeAsyncSession()
    monkeypatch.setattr(link_guard, "async_session", make_async_session_stub(session))

    middleware = LinkGuardMiddleware()
    callback = _build_callback("xn--pple-43d.com")

    handler_called = False

    async def handler(event, data):
        nonlocal handler_called
        handler_called = True
        return "handled"

    result = await middleware(handler, callback, {})

    assert result is None
    assert handler_called is False
    assert callback.answers == [("🚫 Ссылки запрещены.", True)]
    assert callback.message.edits == [
        (
            "🚫 Ссылки запрещены.",
            {"disable_web_page_preview": True, "parse_mode": None},
        )
    ]

    log_entry = next(obj for obj in session.added if isinstance(obj, LogEntry))
    assert log_entry.event_type == "security.link_blocked"
    assert "xn--" in (log_entry.data or {}).get("text_sample", "")
    assert session.committed is True


@pytest.mark.anyio
async def test_admin_login_allows_mixed_script_code(monkeypatch):
    session = FakeAsyncSession()
    monkeypatch.setattr(link_guard, "async_session", make_async_session_stub(session))

    middleware = LinkGuardMiddleware()
    message = _build_message("/admin_login AbС12345")

    handler_called = False

    async def handler(event, data):
        nonlocal handler_called
        handler_called = True
        return "handled"

    result = await middleware(handler, message, {})

    assert result == "handled"
    assert handler_called is True
    assert message.answers == []
    assert session.added == []
    assert session.committed is False


@pytest.mark.anyio
async def test_admin_login_with_url_still_blocked(monkeypatch):
    session = FakeAsyncSession()
    monkeypatch.setattr(link_guard, "async_session", make_async_session_stub(session))

    middleware = LinkGuardMiddleware()
    message = _build_message("/admin_login https://example.com")

    handler_called = False

    async def handler(event, data):
        nonlocal handler_called
        handler_called = True
        return "handled"

    result = await middleware(handler, message, {})

    assert result is None
    assert handler_called is False
    assert message.answers == [
        (
            "🚫 Ссылки в сообщениях запрещены.",
            {"disable_web_page_preview": True, "parse_mode": None},
        )
    ]

    log_entry = next(obj for obj in session.added if isinstance(obj, LogEntry))
    assert log_entry.event_type == "security.link_blocked"
    assert "example.com" in (log_entry.data or {}).get("text_sample", "")
    assert session.committed is True