from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.handlers.user import menu
from bot.services import stats

from tests.conftest import FakeAsyncSession, make_async_session_stub


@pytest.mark.anyio("asyncio")
async def test_get_top_users_returns_entries(monkeypatch):
    rows = [
        SimpleNamespace(
            id=1,
            username="Alice",
            tg_username="alice",
            nuts_balance=300,
            bot_nickname=None,
        ),
        SimpleNamespace(
            id=2,
            username=None,
            tg_username="bob",
            nuts_balance=200,
            bot_nickname="Bobster",
        ),
    ]

    session = FakeAsyncSession(execute_results=[rows])
    monkeypatch.setattr(stats, "async_session", make_async_session_stub(session))

    stats.invalidate_top_users_cache()

    entries = await stats.get_top_users(limit=2)

    assert len(entries) == 2
    assert entries[0].username == "Alice"
    assert entries[1].tg_username == "bob"
    assert session.execute_calls == 1


@pytest.mark.anyio("asyncio")
async def test_profile_top_sends_leaderboard(monkeypatch, message_factory, mock_state):
    sample_entries = [
        stats.TopUserEntry(
            user_id=1,
            username="Alice",
            tg_username="alice",
            balance=300,
            bot_nickname="Queen",
        ),
        stats.TopUserEntry(user_id=2, username=None, tg_username="bob", balance=200),
    ]

    monkeypatch.setattr(menu, "get_top_users", AsyncMock(return_value=sample_entries))

    message = message_factory(text="🏆 Топ игроков")

    await menu.profile_top(message, mock_state)

    assert message.answers
    leaderboard_text = message.answers[0][0]
    assert "🏆 Топ игроков" in leaderboard_text
    assert "Queen" in leaderboard_text
    assert "@bob" in leaderboard_text
    assert (await mock_state.get_data()).get("in_profile") is True