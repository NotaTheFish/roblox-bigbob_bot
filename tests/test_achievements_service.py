from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from backend.services import achievements as achievements_service
from bot.db import Achievement, User
from tests.conftest import FakeAsyncSession


class RecordingSession(FakeAsyncSession):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.scalars_calls: list = []

    async def scalars(self, *args, **kwargs):  # type: ignore[override]
        self.scalars_calls.append(args[0] if args else None)
        return await super().scalars(*args, **kwargs)


@pytest.mark.anyio("asyncio")
async def test_existing_user_achievement_prevents_regrant(monkeypatch):
    achievement = Achievement(
        id=1,
        name="Secret Word",
        reward=10,
        condition_type="secret_word",
        condition_value="Test",
    )
    user = User(id=42, tg_id=111)
    session = RecordingSession(scalars_results=[[achievement.id], [achievement]])

    add_nuts_mock = AsyncMock()
    notify_mock = AsyncMock()
    monkeypatch.setattr(achievements_service, "add_nuts", add_nuts_mock)
    monkeypatch.setattr(achievements_service, "notify_user_achievement_granted", notify_mock)

    result = await achievements_service.evaluate_and_grant_achievements(
        session,
        user=user,
        trigger="secret_word",
        payload={"text": "Test"},
    )

    assert result == []
    assert add_nuts_mock.call_count == 0
    assert notify_mock.call_count == 0
    owned_stmt = session.scalars_calls[0]
    assert owned_stmt is not None
    assert "user_id" in str(owned_stmt)


@pytest.mark.anyio("asyncio")
async def test_secret_word_normalization_grants_once(monkeypatch):
    achievement = Achievement(
        id=2,
        name="Hidden",
        reward=15,
        condition_type="secret_word",
        condition_value="Café",
    )
    user = User(id=7, tg_id=555)

    first_session = RecordingSession(scalars_results=[[], [achievement]])
    second_session = RecordingSession(scalars_results=[[achievement.id], [achievement]])

    add_nuts_mock = AsyncMock()
    notify_mock = AsyncMock()
    monkeypatch.setattr(achievements_service, "add_nuts", add_nuts_mock)
    monkeypatch.setattr(achievements_service, "notify_user_achievement_granted", notify_mock)

    payload = {"text": "Cafe\u0301"}

    granted_first = await achievements_service.evaluate_and_grant_achievements(
        first_session,
        user=user,
        trigger="secret_word",
        payload=payload,
    )

    assert len(granted_first) == 1
    assert any(
        isinstance(added, achievements_service.UserAchievement)
        for added in first_session.added
    )
    assert add_nuts_mock.call_count == 1
    assert notify_mock.call_count == 1

    granted_second = await achievements_service.evaluate_and_grant_achievements(
        second_session,
        user=user,
        trigger="secret_word",
        payload=payload,
    )

    assert granted_second == []
    assert add_nuts_mock.call_count == 1
    assert notify_mock.call_count == 1