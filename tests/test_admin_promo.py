from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from bot.handlers.admin import promo
from bot.states.promo_states import PromoCreateState
from db.models import PromoCode
from tests.conftest import FakeAsyncSession, make_async_session_stub


@pytest.mark.anyio("asyncio")
async def test_admin_promo_finalize_sets_default_promo_type(
    monkeypatch,
    callback_query_factory,
    message_factory,
    mock_state,
):
    session = FakeAsyncSession()
    monkeypatch.setattr(promo, "async_session", make_async_session_stub(session))
    ensure_admin = AsyncMock(return_value=True)
    monkeypatch.setattr(promo, "_ensure_admin_callback", ensure_admin)

    await mock_state.set_state(PromoCreateState.waiting_for_code.state)
    await mock_state.update_data(
        reward_type="discount",
        reward_value=15.5,
        usage_limit=10,
        expiry_days=2,
        code_text="SPRING2024",
    )

    message = message_factory(user_id=99, username="admin")
    call = callback_query_factory(
        "promo:create:next:finalize",
        from_user_id=99,
        message=message,
    )

    await promo.promo_finalize(call, mock_state)

    ensure_admin.assert_awaited_once_with(call)
    assert session.committed is True
    assert session.added, "PromoCode must be persisted"

    created_promo = session.added[0]
    assert isinstance(created_promo, PromoCode)
    assert created_promo.promo_type == "money"
    assert created_promo.code == "SPRING2024"

    assert any("Промокод" in text for text, _ in message.answers)
    assert await mock_state.get_state() is None
    assert call.answers and call.answers[-1] == ("Промокод создан", False)