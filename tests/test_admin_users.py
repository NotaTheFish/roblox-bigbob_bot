from __future__ import annotations

from types import SimpleNamespace

import pytest

from bot.handlers.admin import users
from bot.states.admin_states import GiveTitleState, RemoveTitleState

from tests.conftest import FakeAsyncSession, make_async_session_stub


@pytest.mark.anyio("asyncio")
async def test_give_title_flow_normalizes_titles_and_clears_state(
    monkeypatch, message_factory, mock_state
):
    async def _is_admin_stub(*_args, **_kwargs) -> bool:
        return True

    monkeypatch.setattr(users, "is_admin", _is_admin_stub)

    target_user_id = 777
    user = SimpleNamespace(tg_id=target_user_id, titles=None, selected_title=None)
    session = FakeAsyncSession(scalar_results=[user])
    monkeypatch.setattr(users, "async_session", make_async_session_stub(session))

    await mock_state.set_state(GiveTitleState.waiting_for_title)
    await mock_state.update_data(target_user_id=target_user_id)

    message = message_factory(text="Legendary Hero")

    await users.process_give_title(message, mock_state)

    assert user.titles == ["Legendary Hero"]
    assert user.selected_title == "Legendary Hero"
    assert session.committed is True
    assert message.replies, "Expected confirmation reply from handler"
    assert await mock_state.get_state() is None
    assert await mock_state.get_data() == {}


@pytest.mark.anyio("asyncio")
async def test_remove_title_flow_lists_titles(
    monkeypatch, callback_query_factory, mock_state
):
    async def _is_admin_stub(*_args, **_kwargs) -> bool:
        return True

    monkeypatch.setattr(users, "is_admin", _is_admin_stub)

    target_user_id = 555
    user = SimpleNamespace(tg_id=target_user_id, titles=["Hero", "Champion"], selected_title="Hero")
    session = FakeAsyncSession(scalar_results=[user])
    monkeypatch.setattr(users, "async_session", make_async_session_stub(session))

    call = callback_query_factory(f"remove_title:{target_user_id}")

    await users.remove_title_start(call, mock_state)

    assert await mock_state.get_state() == RemoveTitleState.choosing_title.state
    data = await mock_state.get_data()
    assert data["target_user_id"] == target_user_id
    assert data["title_options"] == ["Hero", "Champion"]
    assert call.message.answers, "Expected list prompt to be sent"


@pytest.mark.anyio("asyncio")
async def test_remove_title_confirm_updates_user(
    monkeypatch, callback_query_factory, mock_state
):
    async def _is_admin_stub(*_args, **_kwargs) -> bool:
        return True

    monkeypatch.setattr(users, "is_admin", _is_admin_stub)

    target_user_id = 999
    titles = ["Legend", "Guardian"]
    user = SimpleNamespace(tg_id=target_user_id, titles=list(titles), selected_title="Legend")
    session = FakeAsyncSession(scalar_results=[user])
    monkeypatch.setattr(users, "async_session", make_async_session_stub(session))

    await mock_state.set_state(RemoveTitleState.confirming)
    await mock_state.update_data(
        target_user_id=target_user_id,
        selected_title="Legend",
        title_options=list(titles),
    )

    call = callback_query_factory("remove_title_confirm")

    await users.remove_title_confirm(call, mock_state)

    assert user.titles == ["Guardian"]
    assert user.selected_title is None
    assert session.committed is True
    assert await mock_state.get_state() is None
    assert call.message.edits, "Expected confirmation edit"
    assert call.bot.sent_messages, "User should be notified"
    args, kwargs = call.bot.sent_messages[-1]
    assert args[0] == target_user_id
    assert "Legend" in args[1]
    assert kwargs.get("parse_mode") == "HTML"