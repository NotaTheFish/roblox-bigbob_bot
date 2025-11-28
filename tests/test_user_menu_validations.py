import pytest
from unittest.mock import AsyncMock

from bot.handlers.user import menu
from bot.states.user_states import ProfileEditState
from tests.conftest import FakeAsyncSession, make_async_session_stub


class _FailingSession:
    async def __aenter__(self):
        raise AssertionError("Session should not be used")

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.anyio("asyncio")
async def test_profile_save_nickname_blocks_links(monkeypatch, message_factory, mock_state):
    message = message_factory(text="http://example.com")

    monkeypatch.setattr(menu, "async_session", lambda: _FailingSession())

    await menu.profile_save_nickname(message, mock_state)

    assert message.answers, "Expected rejection message to be sent"
    text, _ = message.answers[-1]
    assert "Ссылки запрещены" in text
    assert await mock_state.get_state() == ProfileEditState.choosing_action.state


@pytest.mark.anyio("asyncio")
async def test_profile_save_nickname_normalizes_text(monkeypatch, message_factory, mock_state):
    raw_nickname = "Ｔeѕｔ"  # mixed width characters
    normalized = menu._normalize_user_text(raw_nickname)

    user = type("User", (), {"tg_id": 1, "nickname_changed_at": None, "bot_nickname": None})()
    session = FakeAsyncSession(scalar_results=[user])
    monkeypatch.setattr(menu, "async_session", make_async_session_stub(session))

    message = message_factory(text=raw_nickname, user_id=user.tg_id)

    await menu.profile_save_nickname(message, mock_state)

    assert user.bot_nickname == normalized
    assert session.committed is True
    assert any("Ник обновлён" in text for text, _ in message.answers)


@pytest.mark.anyio("asyncio")
async def test_profile_save_about_blocks_links(monkeypatch, message_factory, mock_state):
    message = message_factory(text="Заходи на example.com")

    monkeypatch.setattr(menu, "async_session", lambda: _FailingSession())

    await menu.profile_save_about(message, mock_state)

    assert message.answers, "Expected rejection message to be sent"
    text, _ = message.answers[-1]
    assert "Ссылки запрещены" in text


@pytest.mark.anyio("asyncio")
async def test_profile_save_about_normalizes_text(monkeypatch, message_factory, mock_state):
    raw_about = "ℌ𝔢𝔩𝔩ℴ о боте"
    normalized = menu._normalize_user_text(raw_about)

    user = type(
        "User",
        (),
        {"tg_id": 1, "about_text": None, "about_text_updated_at": None},
    )()
    session = FakeAsyncSession(scalar_results=[user])
    monkeypatch.setattr(menu, "async_session", make_async_session_stub(session))
    monkeypatch.setattr(menu, "evaluate_and_grant_achievements", AsyncMock())

    message = message_factory(text=raw_about, user_id=user.tg_id)

    await menu.profile_save_about(message, mock_state)

    assert user.about_text == normalized
    assert session.committed is True
    assert any("Описание обновлено" in text for text, _ in message.answers)