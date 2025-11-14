from __future__ import annotations

from types import SimpleNamespace

import pytest

from bot.handlers.admin import users
from bot.states.admin_states import GiveTitleState

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