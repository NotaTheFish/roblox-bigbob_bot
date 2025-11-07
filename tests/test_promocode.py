from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from bot.handlers.user import promo
from bot.states.user_states import PromoInputState


@pytest.mark.anyio("asyncio")
async def test_promocode_activation_from_text(monkeypatch, message_factory, mock_state):
    redeem_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(promo, "redeem_promocode", redeem_mock)

    message = message_factory(text="promo2024", user_id=42, username="hero", full_name="Hero User")

    await mock_state.set_state(PromoInputState.waiting_for_code.state)
    await mock_state.update_data(in_profile=True)

    await promo.promo_from_message(message, mock_state)

    redeem_mock.assert_awaited_once()
    assert redeem_mock.await_args.args[1] == "promo2024"
    assert await mock_state.get_state() is None
    assert (await mock_state.get_data()).get("in_profile") is True