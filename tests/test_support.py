from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.handlers.user import support as user_support
from bot.handlers.admin import support as admin_support
from bot.states.admin_states import SupportReplyState

from tests.conftest import FakeAsyncSession, make_async_session_stub


@pytest.mark.anyio("asyncio")
async def test_support_message_forwarded_to_admins(monkeypatch, message_factory, mock_state):
    admin_ids = [101, 202]
    user = SimpleNamespace(id=10, tg_id=555)
    session = FakeAsyncSession(scalar_results=[user], scalars_results=[admin_ids])

    monkeypatch.setattr(user_support, "async_session", make_async_session_stub(session))
    monkeypatch.setattr(user_support, "ROOT_ADMIN_ID", 0)

    message = message_factory(text="Помогите", user_id=555, username="tester", full_name="Test User")
    message.message_id = 42

    await mock_state.set_state("dummy")

    await user_support.handle_support_message(message, mock_state)

    assert session.committed is True
    assert any("Ваше обращение отправлено" in text for text, _ in message.answers)
    recipients = {args[0] for args, _ in message.bot.sent_messages}
    assert recipients == set(admin_ids)
    sent_payloads = [args[1] for args, _ in message.bot.sent_messages]
    assert all("Thread ID" in payload for payload in sent_payloads)
    assert await mock_state.get_state() is None


@pytest.mark.anyio("asyncio")
async def test_admin_support_reply_sends_response(monkeypatch, message_factory, mock_state, mock_bot):
    monkeypatch.setattr(admin_support, "is_admin", AsyncMock(return_value=True))

    admin_session = FakeAsyncSession(scalar_results=[SimpleNamespace(id=10)])
    monkeypatch.setattr(admin_support, "async_session", make_async_session_stub(admin_session))

    await mock_state.set_state(SupportReplyState.waiting_for_message.state)
    await mock_state.update_data(reply_to=777, thread_id=12)

    admin_message = message_factory(
        text="Здравствуйте!", bot=mock_bot, user_id=999, username="admin", full_name="Admin"
    )

    await admin_support.send_support_reply(admin_message, mock_state)

    assert admin_session.committed is True
    assert mock_bot.sent_messages
    args, kwargs = mock_bot.sent_messages[0]
    assert args[0] == 777
    assert "Ответ от поддержки" in args[1]
    assert "Здравствуйте" in args[1]
    assert any("Ответ отправлен" in text for text, _ in admin_message.answers)
    assert await mock_state.get_state() is None