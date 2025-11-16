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


class DummyReferralReward:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class DummyReferral:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id")
        self.referrer_id = kwargs.get("referrer_id")
        self.referred_id = kwargs.get("referred_id")
        self.confirmed = kwargs.get("confirmed", True)

    @property
    def referrer(self):  # pragma: no cover - accessed only in regressions
        raise RuntimeError("Unexpected lazy loading of referrer")


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
    user = SimpleNamespace(id=3, tg_id=55, nuts_balance=200, discount=0)

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


@pytest.mark.anyio("asyncio")
async def test_user_buy_finish_grants_referral_bonus_without_lazy_load(
    monkeypatch, callback_query_factory
):
    product = SimpleNamespace(
        id=11,
        name="Item",
        price=200,
        item_type="item",
        value="cool_hat",
        status="active",
        per_user_limit=None,
        stock_limit=None,
        referral_bonus=25,
        server_id=5,
    )
    user = SimpleNamespace(id=6, tg_id=42, nuts_balance=500, discount=0)
    referral = DummyReferral(id=3, referrer_id=9, referred_id=user.id, confirmed=True)
    referrer_user = SimpleNamespace(id=9, tg_id=999)

    session = FakeAsyncSession(
        scalar_results=[product, user, referral],
        get_results=[referrer_user],
    )
    monkeypatch.setattr(shop, "async_session", make_async_session_stub(session))
    monkeypatch.setattr(shop, "Purchase", DummyPurchase)
    monkeypatch.setattr(shop, "LogEntry", DummyLogEntry)
    monkeypatch.setattr(shop, "ReferralReward", DummyReferralReward)

    subtract_mock = AsyncMock()
    add_mock = AsyncMock()
    monkeypatch.setattr(shop, "subtract_nuts", subtract_mock)
    monkeypatch.setattr(shop, "add_nuts", add_mock)
    monkeypatch.setattr(shop, "check_achievements", AsyncMock())

    call = callback_query_factory("user_buy_ok:11", from_user_id=user.tg_id)
    call.from_user.username = "buyer"
    call.message = SimpleNamespace(answers=[])

    async def message_answer(text, **kwargs):
        call.message.answers.append((text, kwargs))

    call.message.answer = message_answer
    call.bot.send_message = AsyncMock()

    await shop.user_buy_finish(call)

    assert session.committed is True
    assert add_mock.await_count == 1
    _, kwargs = add_mock.await_args_list[0]
    assert kwargs["user"] is referrer_user
    assert kwargs["amount"] == product.referral_bonus
    assert any("реферер получил" in text for text, _ in call.message.answers)
