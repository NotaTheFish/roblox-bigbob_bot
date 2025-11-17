from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest
from zoneinfo import ZoneInfo

from bot.handlers.admin import achievements, logs
from bot.services.admin_logs import LogRecord
from bot.services.profile_renderer import ProfileView, render_profile
from bot.utils.time import to_msk
from tests.conftest import FakeAsyncSession, make_async_session_stub


def test_render_profile_created_at_formatted_in_moscow():
    created_at = datetime(2024, 1, 1, 10, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
    view = ProfileView(heading="Test", created_at=created_at)

    result = render_profile(view)

    expected = to_msk(created_at).strftime("%d.%m.%Y %H:%M")
    assert f"Дата регистрации: {expected}" in result


def test_admin_logs_record_line_uses_moscow_timezone():
    created_at = datetime(2024, 2, 1, 12, 0, tzinfo=ZoneInfo("America/New_York"))
    record = LogRecord(
        id=1,
        created_at=created_at,
        event_type="payment_received",
        message="Пополнение",
        telegram_id=1,
        user_id=2,
        data=None,
    )

    line = logs._format_record_line(1, record)

    expected = to_msk(created_at).strftime("%d.%m %H:%M")
    assert f"<b>{expected}</b>" in line


@pytest.mark.anyio("asyncio")
async def test_achievement_history_formats_time_in_msk(monkeypatch, message_factory):
    earned_at = datetime(2024, 3, 5, 5, 0, tzinfo=ZoneInfo("UTC"))
    entry = SimpleNamespace(earned_at=earned_at, tg_id=111, source="system")
    session = FakeAsyncSession(
        execute_results=[[(entry, "botnick", "player", None, "First Steps")]]
    )
    monkeypatch.setattr(
        achievements, "async_session", make_async_session_stub(session)
    )

    message = message_factory()
    await achievements._send_history(message)

    expected = to_msk(earned_at).strftime("%d.%m %H:%M")
    assert message.answers, "ожидался ответ с историей"
    assert expected in message.answers[0][0]