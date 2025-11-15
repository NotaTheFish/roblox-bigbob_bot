from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.handlers.user import promocode_use

from tests.conftest import FakeAsyncSession, make_async_session_stub
from bot.states.user_states import PromoInputState


@pytest.mark.anyio("asyncio")
async def test_promocode_activation_from_text(monkeypatch, message_factory, mock_state):
    redeem_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(promocode_use, "redeem_promocode", redeem_mock)

    message = message_factory(text="promo2024", user_id=42, username="hero", full_name="Hero User")

    await mock_state.set_state(PromoInputState.waiting_for_code.state)
    await mock_state.update_data(in_profile=True)

    await promocode_use.promo_from_message(message, mock_state)

    redeem_mock.assert_awaited_once()
    assert redeem_mock.await_args.args[1] == "promo2024"
    assert await mock_state.get_state() is None
    assert (await mock_state.get_data()).get("in_profile") is True


@pytest.mark.anyio("asyncio")
async def test_redeem_promocode_logs_notification_failure(
    monkeypatch, message_factory, caplog
):
    monkeypatch.setattr(promocode_use, "ROOT_ADMIN_ID", 5050)

    promo_obj = SimpleNamespace(
        id=1,
        code="FREE",
        active=True,
        max_uses=0,
        uses=0,
        reward_type="nuts",
        reward_amount=10,
        value="10",
        promo_type="money",
        expires_at=None,
    )
    user_obj = SimpleNamespace(id=9, tg_id=88, balance=0, is_blocked=False, discount=0)

    session = FakeAsyncSession(scalar_results=[promo_obj, user_obj, None])
    monkeypatch.setattr(promocode_use, "async_session", make_async_session_stub(session))

    monkeypatch.setattr(promocode_use, "check_achievements", AsyncMock())

    message = message_factory(user_id=88, username="hero", full_name="Hero User")

    async def failing_send_message(*_args, **_kwargs):
        raise RuntimeError("notify failed")

    message.bot.send_message = failing_send_message

    with caplog.at_level("ERROR"):
        result = await promocode_use.redeem_promocode(message, "FREE")

    assert result is True
    assert message.replies
    assert any(
        f"🎉 Промокод {promo_obj.code} активирован" in text
        for text, _ in message.replies
    )
    assert user_obj.balance == 10

    records = [record for record in caplog.records if record.levelname == "ERROR"]
    assert records, "Expected logged error when root admin notification fails"
    record = records[-1]
    assert "Failed to notify root admin" in record.getMessage()
    assert getattr(record, "user_id", None) == 88
    assert getattr(record, "promo_code", None) == "FREE"