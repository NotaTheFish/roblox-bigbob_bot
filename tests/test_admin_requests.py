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
    assert "req-123" in root_notice[0][1]
    assert call.message.edits
    assert call.answers and call.answers[-1] == (None, False)


@pytest.mark.anyio("asyncio")
async def test_admin_request_rejected(monkeypatch, callback_query_factory):
    monkeypatch.setattr(login, "ROOT_ADMIN_ID", 111)

    request = SimpleNamespace(
        telegram_id=77,
        status="pending",
        username="another",
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
    assert "req-999" in root_notice[0][1]
    assert call.message.edits
    assert call.answers and call.answers[-1] == (None, False)