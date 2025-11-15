from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.handlers.admin import payments

from tests.conftest import FakeAsyncSession, make_async_session_stub


@pytest.mark.anyio("asyncio")
async def test_topup_approval_notifies_user(monkeypatch, callback_query_factory):
    monkeypatch.setattr(payments, "is_admin", AsyncMock(return_value=True))

    request = SimpleNamespace(
        id=1,
        status="pending",
        user_id=10,
        telegram_id=77,
        amount=150,
        currency="rub",
        request_id="req-abc",
        payment_id=None,
    )
    user = SimpleNamespace(id=10, tg_id=77, nuts_balance=0)

    session = FakeAsyncSession(get_results=[request, user])
    monkeypatch.setattr(payments, "async_session", make_async_session_stub(session))

    check_achievements_mock = AsyncMock()
    monkeypatch.setattr(payments, "check_achievements", check_achievements_mock)

    call = callback_query_factory("topup_ok:1", from_user_id=500)

    await payments.approve_topup(call)

    assert request.status == "approved"
    assert request.payment_id is not None
    assert user.nuts_balance == 150
    assert session.committed is True
    check_achievements_mock.assert_awaited_once_with(user)
    assert call.message.edits and "✅" in call.message.edits[0][0]
    assert call.answers and call.answers[-1][0] == "✅ Готово"
    assert call.bot.sent_messages
    args, kwargs = call.bot.sent_messages[0]
    assert args[0] == 77
    assert "баланс пополнен" in args[1]