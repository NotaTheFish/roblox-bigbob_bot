from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from bot.handlers.admin import achievements
from bot.states.admin_states import AchievementsState
from db.models import Achievement, User, UserAchievement
from tests.conftest import FakeAsyncSession, make_async_session_stub


@pytest.mark.anyio("asyncio")
async def test_achievement_filter_callback_shows_only_visible(
    monkeypatch, callback_query_factory
):
    visible = Achievement(id=1, name="Visible", reward=10, is_visible=True, condition_type="none")
    load_mock = AsyncMock(return_value=[visible])
    monkeypatch.setattr(achievements, "_load_achievements", load_mock)
    monkeypatch.setattr(achievements, "is_admin", AsyncMock(return_value=True))

    call = callback_query_factory(
        "ach:list:filter:visible:all",
        from_user_id=99,
    )
    await achievements.ach_list_callback(call)

    assert call.message.edits, "Callback should edit the message"
    text, kwargs = call.message.edits[-1]
    assert "Visible" in text
    assert kwargs.get("reply_markup") is not None
    load_mock.assert_awaited_once()
    assert load_mock.await_args.args == ("visible", "all")


@pytest.mark.anyio("asyncio")
async def test_manual_achievement_grant_flow(monkeypatch, message_factory, mock_state):
    user = User(id=1, tg_id=12345, username="player")
    achievement = Achievement(id=5, name="Hero", reward=25, condition_type="none", is_visible=True)

    session_user = FakeAsyncSession(scalar_results=[user])
    session_achievement = FakeAsyncSession(get_results=[achievement], scalar_results=[None])
    session_award = FakeAsyncSession(get_results=[user, achievement])

    monkeypatch.setattr(
        achievements,
        "async_session",
        make_async_session_stub(session_user, session_achievement, session_award),
    )
    add_nuts_mock = AsyncMock()
    monkeypatch.setattr(achievements, "add_nuts", add_nuts_mock)

    await mock_state.set_state(AchievementsState.manual_grant_user.state)
    await achievements.ach_manual_grant_user(
        message_factory(text=str(user.tg_id)),
        mock_state,
    )
    assert (
        await mock_state.get_state() == AchievementsState.manual_grant_achievement.state
    ), "State should switch to selecting achievement"

    await achievements.ach_manual_grant_achievement(
        message_factory(text=str(achievement.id)),
        mock_state,
    )
    assert (
        await mock_state.get_state() == AchievementsState.manual_grant_comment.state
    ), "State should switch to comment"

    await achievements.ach_manual_grant_comment(
        message_factory(text="Поздравляем"),
        mock_state,
    )

    assert session_award.added, "UserAchievement should be persisted"
    granted = session_award.added[0]
    assert isinstance(granted, UserAchievement)
    assert granted.user_id == user.id
    assert granted.achievement_id == achievement.id

    add_nuts_mock.assert_awaited_once()
    assert await mock_state.get_state() is None