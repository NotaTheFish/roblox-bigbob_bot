from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from aiogram import types

from bot.handlers.admin import logs
from bot.keyboards.admin_keyboards import (
    LOGS_ACHIEVEMENTS_BUTTON,
    LOGS_BACK_BUTTON,
    LOGS_NEXT_BUTTON,
    admin_logs_filters_inline,
)
from bot.services.admin_logs import LogCategory, LogPage, LogQuery, LogsRepository
from bot.states.admin_states import AdminLogsState
from db.models import Admin, LogEntry
from tests.conftest import FakeAsyncSession, make_async_session_stub


@pytest.mark.anyio("asyncio")
async def test_logs_repository_limits_page_size():
    base_time = datetime.now(tz=timezone.utc)
    rows: list[LogEntry] = []
    for idx in range(25):
        entry = LogEntry(event_type="payment_received")
        entry.id = idx + 1
        entry.created_at = base_time - timedelta(minutes=idx)
        entry.telegram_id = 1000 + idx
        entry.user_id = idx + 10
        rows.append(entry)

    session = FakeAsyncSession(scalars_results=[rows])
    repo = LogsRepository(session)

    batch = await repo.fetch(LogQuery(category=LogCategory.TOPUPS, offset=0))

    assert len(batch.entries) == 20
    assert batch.next_offset == 20
    assert batch.offset == 0


@pytest.mark.anyio("asyncio")
async def test_next_page_updates_query(monkeypatch, message_factory, mock_state):
    captured: list[LogQuery] = []

    async def fake_collect(query: LogQuery, *_args, **_kwargs) -> LogPage:
        captured.append(query)
        return LogPage(
            entries=[],
            page=query.page,
            total_pages=query.page + 1,
            first_page=1,
            offset=query.offset,
            pages_offsets=(query.offset, query.offset + 1),
            next_offset=query.offset + 1,
            has_prev=query.page > 1,
        )

    async def fake_is_admin(*_args, **_kwargs) -> bool:
        return True

    monkeypatch.setattr(logs, "_collect_logs_page", fake_collect)
    monkeypatch.setattr(logs, "is_admin", fake_is_admin)

    await mock_state.set_state(AdminLogsState.browsing)
    await mock_state.update_data(
        category=LogCategory.TOPUPS.value,
        page=1,
        offsets=[0, 10],
        reply_keyboard_sent=True,
    )

    message = message_factory(text=LOGS_NEXT_BUTTON, user_id=42)
    await logs.next_page(message, mock_state)

    assert captured and captured[-1].page == 2
    assert captured[-1].offset == 10
    assert any("Страница 2/" in text for text, _ in message.answers)


@pytest.mark.anyio("asyncio")
async def test_search_filters_logs(monkeypatch, message_factory, mock_state):
    captured: list[LogQuery] = []

    async def fake_collect(query: LogQuery, *_args, **_kwargs) -> LogPage:
        captured.append(query)
        return LogPage(
            entries=[],
            page=query.page,
            total_pages=query.page,
            first_page=1,
            offset=query.offset,
            pages_offsets=(query.offset,),
            next_offset=None,
            has_prev=False,
        )

    async def fake_is_admin(*_args, **_kwargs) -> bool:
        return True

    async def fake_find_user(query: str):
        return SimpleNamespace(
            id=99,
            tg_id=555,
            username="Tester",
            tg_username="tester",
            bot_nickname="TesterBot",
        )

    monkeypatch.setattr(logs, "_collect_logs_page", fake_collect)
    monkeypatch.setattr(logs, "is_admin", fake_is_admin)
    monkeypatch.setattr(logs, "find_user_by_query", fake_find_user)

    await mock_state.set_state(AdminLogsState.waiting_for_query)

    message = message_factory(text="tester", user_id=10)
    await logs.handle_search_query(message, mock_state)

    assert captured and captured[-1].telegram_id == 555
    assert await mock_state.get_state() == AdminLogsState.browsing.state
    assert any("tester" in text for text, _ in message.answers)


@pytest.mark.anyio("asyncio")
async def test_category_callback_switches_filter(monkeypatch, callback_query_factory, mock_state):
    captured: list[LogQuery] = []

    async def fake_collect(query: LogQuery, *_args, **_kwargs) -> LogPage:
        captured.append(query)
        return LogPage(
            entries=[],
            page=query.page,
            total_pages=query.page,
            first_page=1,
            offset=query.offset,
            pages_offsets=(query.offset,),
            next_offset=None,
            has_prev=False,
        )

    async def fake_is_admin(*_args, **_kwargs) -> bool:
        return True

    monkeypatch.setattr(logs, "_collect_logs_page", fake_collect)
    monkeypatch.setattr(logs, "is_admin", fake_is_admin)

    await mock_state.set_state(AdminLogsState.browsing)
    await mock_state.update_data(category=LogCategory.TOPUPS.value, page=3)

    call = callback_query_factory("logs:category:promocodes", from_user_id=5)
    await logs.category_callback(call, mock_state)

    assert captured and captured[-1].category == LogCategory.PROMOCODES
    assert captured[-1].page == 1


@pytest.mark.anyio("asyncio")
async def test_achievement_button_opens_achievements(monkeypatch, message_factory, mock_state):
    async def fake_is_admin(*_args, **_kwargs) -> bool:
        return True

    called: list[types.Message] = []

    async def fake_admin_menu(message: types.Message):
        called.append(message)

    monkeypatch.setattr(logs, "admin_achievements_menu", fake_admin_menu)
    monkeypatch.setattr(logs, "is_admin", fake_is_admin)

    await mock_state.set_state(AdminLogsState.browsing)
    await mock_state.update_data(category=LogCategory.TOPUPS.value, page=2)

    message = message_factory(text=LOGS_ACHIEVEMENTS_BUTTON, user_id=99)
    await logs.open_admin_achievements(message, mock_state)

    assert called and called[-1] is message
    assert await mock_state.get_state() is None


@pytest.mark.anyio("asyncio")
async def test_back_button_clears_state(monkeypatch, message_factory, mock_state):
    async def fake_is_admin(*_args, **_kwargs) -> bool:
        return True

    monkeypatch.setattr(logs, "is_admin", fake_is_admin)

    await mock_state.set_state(AdminLogsState.browsing)
    await mock_state.update_data(category=LogCategory.TOPUPS.value, page=2)

    message = message_factory(text=LOGS_BACK_BUTTON, user_id=77)
    await logs.exit_logs_menu(message, mock_state)

    assert await mock_state.get_state() is None
    assert message.answers and any("главное меню" in text.lower() for text, _ in message.answers)


def test_logs_filters_include_promocode_button():
    markup = admin_logs_filters_inline(LogCategory.TOPUPS)
    button_texts = [button.text for row in markup.inline_keyboard for button in row]
    assert any(text.startswith("🎟 Промокоды") for text in button_texts)


def test_security_category_visible_only_for_head_admin(monkeypatch):
    monkeypatch.setattr(logs, "ADMIN_ROOT_IDS", [99])

    assert LogCategory.SECURITY not in logs._visible_categories_for(5)
    assert LogCategory.SECURITY in logs._visible_categories_for(99)


@pytest.mark.anyio("asyncio")
async def test_demote_confirm_removes_admin(monkeypatch, callback_query_factory, mock_state):
    admin = Admin(telegram_id=77, is_root=False)
    session = FakeAsyncSession(scalar_results=[admin])
    monkeypatch.setattr(logs, "async_session", make_async_session_stub(session))

    async def fake_collect(query: LogQuery, *_args, **_kwargs) -> LogPage:
        return LogPage(
            entries=[],
            page=query.page,
            total_pages=query.page,
            first_page=1,
            offset=query.offset,
            pages_offsets=(query.offset,),
            next_offset=None,
            has_prev=False,
        )

    async def fake_is_admin(*_args, **_kwargs) -> bool:
        return True

    monkeypatch.setattr(logs, "_collect_logs_page", fake_collect)
    monkeypatch.setattr(logs, "is_admin", fake_is_admin)
    monkeypatch.setattr(logs, "ROOT_ADMIN_ID", 1)

    await mock_state.set_state(AdminLogsState.browsing)
    await mock_state.update_data(
        category=LogCategory.TOPUPS.value,
        page=1,
        telegram_id=77,
    )

    call = callback_query_factory("demote_admin_confirm:77", from_user_id=1)
    await logs.demote_confirm(call, mock_state)

    assert session.deleted and session.deleted[0] is admin
    log_entry = next(obj for obj in session.added if isinstance(obj, LogEntry))
    assert log_entry.event_type == "admin_demoted"
    assert call.bot.sent_messages, "Ожидалось уведомление демотируемому администратору"