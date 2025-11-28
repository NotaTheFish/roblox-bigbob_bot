import pytest

from bot.handlers.admin import users as admin_users_handlers
from bot.handlers.user import messages as user_messages_handlers
from bot.middleware.banned import BannedMiddleware
from bot.services.reply_keyboard import (
    clear_reply_keyboard_flag,
    mark_reply_keyboard_removed,
    was_reply_keyboard_removed,
)
from bot.texts.block import UNBLOCK_NOTIFICATION_TEXT
from db.models import User
from tests.conftest import FakeAsyncSession, make_async_session_stub


@pytest.mark.anyio
async def test_fallback_restores_keyboard_when_missing(
    message_factory, monkeypatch
):
    user = User(bot_user_id="bot-1", tg_id=111, verified=True, is_blocked=False)
    session = FakeAsyncSession(scalar_results=[user, None])
    monkeypatch.setattr(
        user_messages_handlers,
        "async_session",
        make_async_session_stub(session),
    )

    mark_reply_keyboard_removed(user.tg_id)
    message = message_factory(user_id=user.tg_id)

    await user_messages_handlers.restore_reply_keyboard_on_plain_text(message)

    assert was_reply_keyboard_removed(user.tg_id) is False
    assert message.bot.sent_messages[-1][0][:2] == (user.tg_id, "↩ Главное меню")
    reply_markup = message.bot.sent_messages[-1][1]["reply_markup"]
    assert reply_markup.keyboard[-1][0].text != "🛠 Режим админа"


@pytest.mark.anyio
async def test_unblock_notification_restores_keyboard(
    callback_query_factory, monkeypatch
):
    user = User(bot_user_id="bot-2", tg_id=222, verified=True, is_blocked=True)
    session = FakeAsyncSession(scalar_results=[user])
    monkeypatch.setattr(
        admin_users_handlers,
        "async_session",
        make_async_session_stub(session),
    )

    async def fake_unblock_user(session, *, user):
        user.is_blocked = False

    monkeypatch.setattr(admin_users_handlers, "unblock_user_record", fake_unblock_user)
    async def fake_is_admin(_uid):
        return False

    monkeypatch.setattr(admin_users_handlers, "is_admin", fake_is_admin)

    mark_reply_keyboard_removed(user.tg_id)
    callback = callback_query_factory("banlist:unban", message=None)

    await admin_users_handlers._process_unblock_user(callback, user.tg_id)

    assert was_reply_keyboard_removed(user.tg_id) is False
    assert callback.bot.sent_messages[-1][0][:2] == (user.tg_id, UNBLOCK_NOTIFICATION_TEXT)
    reply_markup = callback.bot.sent_messages[-1][1]["reply_markup"]
    assert reply_markup.keyboard[-1][0].text != "🛠 Режим админа"


@pytest.mark.anyio
async def test_ban_callback_marks_keyboard_removal(callback_query_factory):
    middleware = BannedMiddleware()
    callback = callback_query_factory("ban:notify")
    callback.message.bot = callback.bot

    await middleware._notify_callback(callback, reply_markup=None)

    assert was_reply_keyboard_removed(callback.from_user.id) is True
    clear_reply_keyboard_flag(callback.from_user.id)