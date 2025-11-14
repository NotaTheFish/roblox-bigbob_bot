from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.handlers.user import shop

from tests.conftest import FakeAsyncSession, make_async_session_stub


class DummyPurchase:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id")
        self.request_id = kwargs.get("request_id")
        for key, value in kwargs.items():
            setattr(self, key, value)


class DummyLogEntry:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


@pytest.mark.anyio("asyncio")
async def test_user_buy_finish_logs_root_notification_failure(
    monkeypatch, callback_query_factory, caplog
):
    monkeypatch.setattr(shop, "ROOT_ADMIN_ID", 4040)

    product = SimpleNamespace(
        id=7,
        name="VIP",
        price=100,
        item_type="privilege",
        value="vip",
        status="active",
        per_user_limit=None,
        stock_limit=None,
        referral_bonus=0,
        server_id=1,
    )
    user = SimpleNamespace(id=3, tg_id=55, balance=200, discount=0)

    session = FakeAsyncSession(
        scalar_results=[product, user, None],
    )
    monkeypatch.setattr(shop, "async_session", make_async_session_stub(session))
    monkeypatch.setattr(shop, "Purchase", DummyPurchase)
    monkeypatch.setattr(shop, "LogEntry", DummyLogEntry)
    monkeypatch.setattr(shop, "check_achievements", AsyncMock())

    call = callback_query_factory("user_buy_ok:7", from_user_id=user.tg_id)
    call.from_user.username = "buyer"
    call.message = SimpleNamespace(answers=[])

    async def message_answer(text, **kwargs):
        call.message.answers.append((text, kwargs))

    call.message.answer = message_answer

    original_send_message = call.bot.send_message

    async def conditional_send_message(*args, **kwargs):
        if args and args[0] == shop.ROOT_ADMIN_ID:
            raise RuntimeError("notify failed")
        return await original_send_message(*args, **kwargs)

    call.bot.send_message = conditional_send_message

    with caplog.at_level("ERROR"):
        await shop.user_buy_finish(call)

    assert session.committed is True
    assert call.message.answers
    assert any("Покупка успешна" in text for text, _ in call.message.answers)

    records = [record for record in caplog.records if record.levelname == "ERROR"]
    assert records, "Expected logged error when root admin notification fails"
    record = records[-1]
    assert "Failed to notify root admin" in record.getMessage()
    assert getattr(record, "user_id", None) == user.tg_id
    assert getattr(record, "product_id", None) == product.id
