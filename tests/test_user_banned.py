"""Tests for ban appeal handlers."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from bot.handlers.user import banned as banned_handlers
from bot.keyboards.ban_appeal import BAN_APPEAL_CALLBACK
from bot.states.user_states import BanAppealState
from db.models import LogEntry, User
from tests.conftest import FakeAsyncSession, make_async_session_stub


@pytest.mark.anyio
async def test_start_ban_appeal_blocks_when_already_open(
    callback_query_factory,
    mock_state,
    monkeypatch,
):
    user = User(
        id=1,
        tg_id=123,
        is_blocked=True,
        appeal_open=True,
        ban_appeal_submitted=False,
    )
    session = FakeAsyncSession(scalar_results=[user])
    monkeypatch.setattr(
        banned_handlers,
        "async_session",
        make_async_session_stub(session),
    )

    callback = callback_query_factory(BAN_APPEAL_CALLBACK, message=None)

    await banned_handlers.start_ban_appeal(callback, mock_state, ban_appeal_was_open=True)

    assert callback.answers == [("Апелляция уже подана", True)]
    assert await mock_state.get_state() is None


@pytest.mark.anyio
async def test_start_ban_appeal_allows_first_open_even_if_flag_set(
    callback_query_factory,
    mock_state,
    monkeypatch,
):
    user = User(
        id=1,
        tg_id=123,
        is_blocked=True,
        appeal_open=True,
        ban_appeal_submitted=False,
    )
    session = FakeAsyncSession(scalar_results=[user])
    monkeypatch.setattr(
        banned_handlers,
        "async_session",
        make_async_session_stub(session),
    )

    callback = callback_query_factory(BAN_APPEAL_CALLBACK, message=None)

    await banned_handlers.start_ban_appeal(callback, mock_state, ban_appeal_was_open=False)

    assert await mock_state.get_state() == BanAppealState.waiting_for_message.state
    assert callback.answers[-1] == (None, False)


@pytest.mark.anyio
async def test_start_ban_appeal_blocks_after_submission(
    callback_query_factory,
    mock_state,
    monkeypatch,
):
    user = User(
        id=1,
        tg_id=123,
        is_blocked=True,
        appeal_open=False,
        ban_appeal_submitted=True,
    )
    session = FakeAsyncSession(scalar_results=[user])
    monkeypatch.setattr(
        banned_handlers,
        "async_session",
        make_async_session_stub(session),
    )

    callback = callback_query_factory(BAN_APPEAL_CALLBACK, message=None)

    await banned_handlers.start_ban_appeal(callback, mock_state)

    assert callback.answers == [("Апелляция уже подана", True)]
    assert await mock_state.get_state() is None


@pytest.mark.anyio
async def test_process_ban_appeal_updates_flags_and_notifies(
    message_factory,
    mock_state,
    mock_bot,
    monkeypatch,
):
    user = User(
        id=5,
        tg_id=999,
        is_blocked=True,
        appeal_open=True,
        ban_appeal_submitted=False,
    )
    session = FakeAsyncSession(
        scalar_results=[user],
        scalars_results=[[111]],
    )
    monkeypatch.setattr(
        banned_handlers,
        "async_session",
        make_async_session_stub(session),
    )

    message = message_factory(text="Пожалуйста разблокируйте", user_id=999)

    await banned_handlers.process_ban_appeal(message, mock_state)

    assert user.appeal_open is False
    assert user.ban_appeal_submitted is True
    assert isinstance(user.appeal_submitted_at, datetime)
    assert isinstance(user.ban_appeal_at, datetime)
    assert user.appeal_submitted_at.tzinfo == timezone.utc
    assert user.ban_appeal_at.tzinfo == timezone.utc

    assert await mock_state.get_state() is None
    assert message.answers[-1][0] == "Апелляция отправлена"

    assert session.flushed is True
    assert session.committed is True
    assert any(isinstance(obj, LogEntry) for obj in session.added)
    assert mock_bot.sent_messages  # at least one admin notification was sent