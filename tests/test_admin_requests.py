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


@pytest.mark.anyio("asyncio")
async def test_admin_login_notification_error_logged(
    monkeypatch, message_factory, caplog
):
    monkeypatch.setattr(login, "ROOT_ADMIN_ID", 1010)

    is_admin_session = FakeAsyncSession(scalar_results=[None])
    request_session = FakeAsyncSession(scalar_results=[None])
    monkeypatch.setattr(
        login,
        "async_session",
        make_async_session_stub(is_admin_session, request_session),
    )

    message = message_factory(user_id=77, username="tester", full_name="Tester")

    async def failing_send_message(*_args, **_kwargs):
        raise RuntimeError("network down")

    message.bot.send_message = failing_send_message

    with caplog.at_level("ERROR"):
        success = await login._process_admin_code(message, "DEFAULT")

    assert success is True
    assert message.replies
    assert any("Запрос" in reply[0] for reply in message.replies)

    records = [record for record in caplog.records if record.levelname == "ERROR"]
    assert records, "Expected error log when notification fails"
    record = records[-1]
    assert "Failed to notify root admin" in record.getMessage()
    assert getattr(record, "user_id", None) == 77
    admin_request = next(
        obj for obj in request_session.added if obj.__class__.__name__ == "AdminRequest"
    )
    assert getattr(record, "request_id", None) == admin_request.request_id


@pytest.mark.anyio("asyncio")
async def test_admin_request_callback_logs_notification_error(
    monkeypatch, callback_query_factory, caplog
):
    monkeypatch.setattr(login, "ROOT_ADMIN_ID", 2020)

    request = SimpleNamespace(
        telegram_id=42,
        status="pending",
        username="tester",
        full_name="Tester",
        request_id="req-123",
    )

    session = FakeAsyncSession(scalar_results=[request])
    monkeypatch.setattr(login, "async_session", make_async_session_stub(session))

    call = callback_query_factory("approve_admin:req-123", from_user_id=500)

    original_send_message = call.bot.send_message

    async def conditional_send_message(*args, **kwargs):
        if args and args[0] == login.ROOT_ADMIN_ID:
            raise RuntimeError("notification failed")
        return await original_send_message(*args, **kwargs)

    call.bot.send_message = conditional_send_message

    with caplog.at_level("ERROR"):
        await login.admin_request_callback(call)

    assert session.committed is True
    assert call.bot.sent_messages  # user notified successfully
    assert all(args[0] != login.ROOT_ADMIN_ID for args, _ in call.bot.sent_messages)

    records = [record for record in caplog.records if record.levelname == "ERROR"]
    assert records, "Expected error log when root admin notification fails"
    record = records[-1]
    assert "Failed to notify root admin" in record.getMessage()
    assert getattr(record, "user_id", None) == 42
    assert getattr(record, "request_id", None) == "req-123"