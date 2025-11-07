from __future__ import annotations

from types import SimpleNamespace

import pytest

from bot.handlers.admin import login

from tests.conftest import FakeAsyncSession, make_async_session_stub


@pytest.mark.anyio("asyncio")
async def test_admin_request_approved(monkeypatch, callback_query_factory):
    monkeypatch.setattr(login, "ROOT_ADMIN_ID", 999)

    request = SimpleNamespace(
        telegram_id=42,
        status="pending",
        username="tester",
        full_name="Tester",
        request_id="req-123",
    )

    session = FakeAsyncSession(scalar_results=[request])
    monkeypatch.setattr(login, "async_session", make_async_session_stub(session))

    call = callback_query_factory("approve_admin:req-123", from_user_id=100)

    await login.admin_request_callback(call)

    assert request.status == "approved"
    assert session.committed is True
    assert call.bot.sent_messages
    user_notice, root_notice = call.bot.sent_messages[:2]
    assert user_notice[0][0] == 42
    assert "одобрена" in user_notice[0][1]
    assert root_notice[0][0] == 999
    assert "<code>req-123</code>" in root_notice[0][1]
    assert "<b>Tester</b>" in root_notice[0][1]
    assert root_notice[1]["parse_mode"] == "HTML"
    assert call.message.edits
    edit_text, edit_kwargs = call.message.edits[-1]
    assert "<code>req-123</code>" in edit_text
    assert "<b>Tester</b>" in edit_text
    assert edit_kwargs.get("parse_mode") == "HTML"
    assert call.answers and call.answers[-1] == (None, False)


@pytest.mark.anyio("asyncio")
async def test_admin_request_rejected(monkeypatch, callback_query_factory):
    monkeypatch.setattr(login, "ROOT_ADMIN_ID", 111)

    request = SimpleNamespace(
        telegram_id=77,
        status="pending",
        username="another",
        full_name="Another User",
        request_id="req-999",
    )

    session = FakeAsyncSession(scalar_results=[request])
    monkeypatch.setattr(login, "async_session", make_async_session_stub(session))

    call = callback_query_factory("reject_admin:req-999", from_user_id=500)

    await login.admin_request_callback(call)

    assert request.status == "denied"
    assert session.committed is True
    assert call.bot.sent_messages
    user_notice, root_notice = call.bot.sent_messages[:2]
    assert user_notice[0][0] == 77
    assert "отказано" in user_notice[0][1]
    assert root_notice[0][0] == 111
    assert "<code>req-999</code>" in root_notice[0][1]
    assert "<b>Another User</b>" in root_notice[0][1]
    assert root_notice[1]["parse_mode"] == "HTML"
    assert call.message.edits
    edit_text, edit_kwargs = call.message.edits[-1]
    assert "<code>req-999</code>" in edit_text
    assert "<b>Another User</b>" in edit_text
    assert edit_kwargs.get("parse_mode") == "HTML"
    assert call.answers and call.answers[-1] == (None, False)


@pytest.mark.anyio("asyncio")
async def test_admin_login_request_sends_full_name(monkeypatch, message_factory):
    monkeypatch.setattr(login, "ROOT_ADMIN_ID", 555)

    is_admin_session = FakeAsyncSession(scalar_results=[None])
    request_session = FakeAsyncSession(scalar_results=[None])
    monkeypatch.setattr(
        login,
        "async_session",
        make_async_session_stub(is_admin_session, request_session),
    )

    message = message_factory(user_id=10, username=None, full_name="Display Name")

    success = await login._process_admin_code(message, "DEFAULT")

    assert success is True
    admin_request = next(
        obj for obj in request_session.added if obj.__class__.__name__ == "AdminRequest"
    )
    assert admin_request.full_name == "Display Name"
    assert admin_request.username is None

    assert message.bot.sent_messages
    root_message = message.bot.sent_messages[0]
    assert root_message[0][0] == 555
    assert "<b>Display Name</b>" in root_message[0][1]
    assert "—" in root_message[0][1]
    assert root_message[1]["parse_mode"] == "HTML"
    assert message.replies
    assert "Запрос отправлен" in message.replies[-1][0]