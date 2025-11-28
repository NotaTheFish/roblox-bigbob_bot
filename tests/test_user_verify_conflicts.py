import pytest

from bot.db import User
from bot.handlers.user import verify
from bot.states.verify_state import VerifyState
from tests.conftest import (
    FakeAsyncSession,
    MockCallbackMessage,
    MockCallbackQuery,
    MockFSMContext,
    make_async_session_stub,
)


@pytest.mark.anyio
async def test_reject_reusing_roblox_account(monkeypatch, mock_bot):
    user = User(bot_user_id="bot_new", tg_id=2, username="newbie", code="54321")
    existing_user = User(
        bot_user_id="bot_existing",
        tg_id=3,
        username="owner",
        roblox_id="999",
    )

    lookup_session = FakeAsyncSession(scalar_results=[user])
    verification_session = FakeAsyncSession(
        scalar_results=[user, existing_user, None]
    )

    monkeypatch.setattr(
        verify,
        "async_session",
        make_async_session_stub(lookup_session, verification_session),
    )
    monkeypatch.setattr(
        verify, "get_roblox_profile", lambda _username: ("desc 54321", "", "999")
    )

    state = MockFSMContext()
    await state.set_state(VerifyState.waiting_for_check)
    call = MockCallbackQuery(
        "check_verify",
        bot=mock_bot,
        from_user_id=2,
        message=MockCallbackMessage(),
    )

    await verify.check_verify(call, state)

    assert any("уже привязан" in (text or "") for text, _ in call.message.answers)
    assert not user.verified
    assert user.roblox_id is None
    assert verification_session.committed is False
    assert await state.get_state() is None


@pytest.mark.anyio
async def test_reject_switching_linked_telegram(monkeypatch, mock_bot):
    user = User(
        bot_user_id="bot_new",
        tg_id=4,
        username="current",
        code="11111",
        roblox_id="111",
    )

    lookup_session = FakeAsyncSession(scalar_results=[user])
    verification_session = FakeAsyncSession(scalar_results=[user, None, None])

    monkeypatch.setattr(
        verify,
        "async_session",
        make_async_session_stub(lookup_session, verification_session),
    )
    monkeypatch.setattr(
        verify, "get_roblox_profile", lambda _username: ("desc 11111", "", "222")
    )

    state = MockFSMContext()
    await state.set_state(VerifyState.waiting_for_check)
    call = MockCallbackQuery(
        "check_verify",
        bot=mock_bot,
        from_user_id=4,
        message=MockCallbackMessage(),
    )

    await verify.check_verify(call, state)

    assert any("уже привязан" in (text or "") for text, _ in call.message.answers)
    assert user.roblox_id == "111"
    assert not user.verified
    assert verification_session.committed is False
    assert await state.get_state() is None