import pytest
from unittest.mock import AsyncMock

from aiogram.filters import CommandObject

from bot.handlers.user import start as start_handler
from db import User
from tests.conftest import FakeAsyncSession, make_async_session_stub


@pytest.mark.anyio("asyncio")
async def test_start_cmd_uses_command_args(monkeypatch, message_factory):
    message = message_factory(text="/start refer-code", user_id=101, username="newbie")
    referrer = User(
        bot_user_id="BOT-REF",
        tg_id=999,
        tg_username="referrer",
        username=None,
        roblox_id=None,
        balance=0,
        verified=True,
        code=None,
        is_blocked=False,
    )
    referrer.id = 5

    session = FakeAsyncSession(scalar_results=[None])
    monkeypatch.setattr(start_handler, "async_session", make_async_session_stub(session))
    monkeypatch.setattr(start_handler, "_generate_bot_user_id", AsyncMock(return_value="BOT-42"))

    captured: dict = {}

    async def ensure_code_stub(_session, user):
        user.referral_code = "self-code"
        return "self-code"

    async def find_referrer_stub(_session, code):
        captured["code"] = code
        return referrer

    async def attach_referral_stub(_session, ref, user):
        captured["attached"] = (ref, user)
        return object()

    monkeypatch.setattr(start_handler, "ensure_referral_code", ensure_code_stub)
    monkeypatch.setattr(start_handler, "find_referrer_by_code", find_referrer_stub)
    monkeypatch.setattr(start_handler, "attach_referral", attach_referral_stub)

    command = CommandObject(command="start", args="refer-code")
    await start_handler.start_cmd(message, command)

    assert captured["code"] == "refer-code"
    assert isinstance(captured["attached"][1], User)
    assert session.committed is True
    assert message.answers
    assert "Добро пожаловать" in message.answers[-1][0]
    assert message.bot.sent_messages, "Referrer notification should be sent"


@pytest.mark.anyio("asyncio")
async def test_start_cmd_handles_missing_command(monkeypatch, message_factory):
    message = message_factory(text="/start from-message", user_id=202, username="withoutcmd")
    referrer = User(
        bot_user_id="BOT-REF2",
        tg_id=111,
        tg_username="ref_two",
        username=None,
        roblox_id=None,
        balance=0,
        verified=True,
        code=None,
        is_blocked=False,
    )
    referrer.id = 15

    session = FakeAsyncSession(scalar_results=[None])
    monkeypatch.setattr(start_handler, "async_session", make_async_session_stub(session))
    monkeypatch.setattr(start_handler, "_generate_bot_user_id", AsyncMock(return_value="BOT-99"))

    captured: dict = {}

    async def ensure_code_stub(_session, user):
        user.referral_code = "self-code"
        return "self-code"

    async def find_referrer_stub(_session, code):
        captured["code"] = code
        return referrer

    async def attach_referral_stub(_session, ref, user):
        captured["attached"] = (ref, user)
        return object()

    monkeypatch.setattr(start_handler, "ensure_referral_code", ensure_code_stub)
    monkeypatch.setattr(start_handler, "find_referrer_by_code", find_referrer_stub)
    monkeypatch.setattr(start_handler, "attach_referral", attach_referral_stub)

    await start_handler.start_cmd(message, command=None)

    assert captured["code"] == "from-message"
    assert isinstance(captured["attached"][1], User)
    assert session.committed is True
    assert message.answers
    assert "Добро пожаловать" in message.answers[-1][0]
    assert message.bot.sent_messages, "Referrer notification should be sent"