from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from bot.utils import achievement_checker
from db.models import Achievement, LogEntry, User
from tests.conftest import FakeAsyncSession, make_async_session_stub


@pytest.mark.anyio("asyncio")
async def test_check_achievements_logs_grants(monkeypatch):
    user = User(id=1, tg_id=10)
    db_user = User(id=1, tg_id=10)
    achievement = Achievement(
        id=5,
        name="Первое достижение",
        reward=25,
        condition_type="none",
    )

    session = FakeAsyncSession(
        scalar_results=[db_user],
        scalars_results=[[], [achievement]],
    )

    monkeypatch.setattr(
        achievement_checker, "async_session", make_async_session_stub(session)
    )
    add_nuts_mock = AsyncMock()
    monkeypatch.setattr(achievement_checker, "add_nuts", add_nuts_mock)

    await achievement_checker.check_achievements(user)

    log_entry = next(obj for obj in session.added if isinstance(obj, LogEntry))
    assert log_entry.event_type == "achievement_granted"
    assert log_entry.message == "Достижение Первое достижение"
    assert log_entry.data == {
        "achievement_id": achievement.id,
        "reward": achievement.reward,
        "source": "check_achievements",
    }
    assert session.committed is True