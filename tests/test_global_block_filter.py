"""Tests for the global block filter handlers."""

from __future__ import annotations

import pytest

from aiogram.dispatcher.event import bases as event_bases

from bot.handlers import global_block_filter
from db.models import User


@pytest.mark.anyio
async def test_blocked_message_is_intercepted(monkeypatch, message_factory):
    user = User(id=10, tg_id=12345, is_blocked=True)
    message = message_factory(user_id=user.tg_id)

    async def fake_get_user(tg_id: int, **_kwargs):
        assert tg_id == user.tg_id
        return user

    monkeypatch.setattr(global_block_filter, "get_user", fake_get_user)

    result = await global_block_filter.block_banned_message(message, data={})

    assert message.answers == [("❌ Вы заблокированы.", {"reply_markup": None})]
    assert result is not event_bases.UNHANDLED  # Stops further handler propagation