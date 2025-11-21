"""Tests for the global block filter handlers."""

from __future__ import annotations

import pytest

from aiogram.dispatcher.event import bases as event_bases

from bot.handlers import global_block_filter
from bot.keyboards.ban_appeal import BAN_APPEAL_CALLBACK
from bot.states.user_states import BanAppealState
from db.models import User


@pytest.mark.anyio
async def test_blocked_message_is_intercepted(monkeypatch, message_factory):
    user = User(id=10, tg_id=12345, is_blocked=True)
    message = message_factory(user_id=user.tg_id)

    async def fake_get_user(tg_id: int, **_kwargs):
        assert tg_id == user.tg_id
        return user

    monkeypatch.setattr(global_block_filter, "get_user", fake_get_user)

    result = await global_block_filter.block_banned_message(
        message,
        blocked_user=user,
        data={},
    )

    assert message.answers == [("❌ Вы заблокированы.", {"reply_markup": None})]
    assert result is not event_bases.UNHANDLED  # Stops further handler propagation


@pytest.mark.anyio
async def test_blocked_callback_is_intercepted(monkeypatch, callback_query_factory):
    user = User(id=11, tg_id=54321, is_blocked=True)
    callback = callback_query_factory("other", from_user_id=user.tg_id)

    async def fake_get_user(tg_id: int, **_kwargs):
        assert tg_id == user.tg_id
        return user

    monkeypatch.setattr(global_block_filter, "get_user", fake_get_user)

    result = await global_block_filter.BlockedUserFilter()(callback)

    assert result == {"blocked_user": user}


@pytest.mark.anyio
async def test_ban_appeal_callback_is_not_blocked(monkeypatch, callback_query_factory):
    user = User(id=12, tg_id=777, is_blocked=True)
    callback = callback_query_factory(BAN_APPEAL_CALLBACK, from_user_id=user.tg_id)

    async def fake_get_user(tg_id: int, **_kwargs):
        assert tg_id == user.tg_id
        return user

    monkeypatch.setattr(global_block_filter, "get_user", fake_get_user)

    result = await global_block_filter.BlockedUserFilter()(callback)

    assert result is False  # Allows the ban appeal handler to run


@pytest.mark.anyio
async def test_ban_appeal_state_is_not_blocked(monkeypatch, message_factory, mock_state):
    user = User(id=13, tg_id=888, is_blocked=True)
    message = message_factory(user_id=user.tg_id)

    async def fake_get_user(tg_id: int, **_kwargs):
        assert tg_id == user.tg_id
        return user

    await mock_state.set_state(BanAppealState.waiting_for_message)
    monkeypatch.setattr(global_block_filter, "get_user", fake_get_user)

    result = await global_block_filter.BlockedUserFilter()(message, state=mock_state)

    assert result is False  # Allows the appeal message handler to run