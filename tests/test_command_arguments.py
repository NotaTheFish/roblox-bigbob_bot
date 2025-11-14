import asyncio
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.filters import CommandObject

import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault("TELEGRAM_TOKEN", "test:token")
os.environ.setdefault("ADMIN_LOGIN_PASSWORD", "DEFAULT")

from bot.db import AdminRequest
from bot.handlers.admin import login
from bot.handlers.user import promo
from bot.states.user_states import PromoInputState
from bot.states.admin_states import AdminLoginState


class DummyBot:
    def __init__(self):
        self.sent_messages = []

    async def send_message(self, *args, **kwargs):
        self.sent_messages.append((args, kwargs))


class DummyMessage:
    def __init__(self, user_id: int = 1, username: str | None = "user", text: str | None = None):
        self.from_user = SimpleNamespace(id=user_id, username=username)
        self.bot = DummyBot()
        self.replies: list[tuple[str, dict]] = []
        self.text = text

    async def reply(self, text: str, **kwargs):
        self.replies.append((text, kwargs))
        return text


class DummyFSMContext:
    def __init__(self):
        self._state: str | None = None
        self._data: dict = {}

    async def set_state(self, state):
        if state is None:
            self._state = None
        else:
            self._state = getattr(state, "state", state)

    async def get_state(self):
        return self._state

    async def clear(self):
        self._state = None
        self._data = {}

    async def update_data(self, **kwargs):
        self._data.update(kwargs)
        return dict(self._data)

    async def get_data(self):
        return dict(self._data)


class DummySession:
    def __init__(self, scalar_results: list):
        self._scalar_iter = iter(scalar_results)
        self.added = []
        self.committed = False
        self.flushed = False

    async def scalar(self, *_args, **_kwargs):
        return next(self._scalar_iter, None)

    def add(self, obj):
        if isinstance(obj, AdminRequest) and getattr(obj, "request_id", None) is None:
            obj.request_id = f"req-{len(self.added) + 1}"
        self.added.append(obj)

    async def commit(self):
        self.committed = True

    async def flush(self):
        self.flushed = True

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


def make_session_factory(sessions: list[DummySession]):
    session_iter = iter(sessions)

    def factory():
        return next(session_iter)

    return factory


def test_admin_login_without_args(monkeypatch):
    message = DummyMessage()
    command = CommandObject(command="admin_login", args=None)

    monkeypatch.setattr(login, "ADMIN_LOGIN_PASSWORD", "SECRET")

    asyncio.run(login.admin_login(message, command))

    assert message.replies
    assert message.replies[0][0].startswith("Введите секретный код")


def test_admin_login_with_valid_code(monkeypatch):
    message = DummyMessage(user_id=42, username="tester")
    command = CommandObject(command="admin_login", args="SECRET")

    monkeypatch.setattr(login, "ADMIN_LOGIN_PASSWORD", "SECRET")
    monkeypatch.setattr(login, "ROOT_ADMIN_ID", 999)

    sessions = [
        DummySession([None]),  # is_admin check
        DummySession([None]),  # pending request check
    ]

    factory = make_session_factory(sessions)

    class AsyncSessionWrapper:
        def __init__(self, session):
            self._session = session

        async def __aenter__(self):
            return await self._session.__aenter__()

        async def __aexit__(self, exc_type, exc, tb):
            return await self._session.__aexit__(exc_type, exc, tb)

    def async_session_stub():
        session = factory()
        return AsyncSessionWrapper(session)

    monkeypatch.setattr(login, "async_session", async_session_stub)

    asyncio.run(login.admin_login(message, command))

    assert sessions[1].committed is True
    created_request = sessions[1].added[0]
    assert isinstance(created_request, AdminRequest)
    request_id = created_request.request_id
    assert request_id
    assert any(
        text.startswith("⌛ Запрос отправлен") for text, _ in message.replies
    )
    assert message.bot.sent_messages
    args, kwargs = message.bot.sent_messages[0]
    assert request_id in args[1]
    reply_markup = kwargs.get("reply_markup")
    assert reply_markup is not None
    buttons = reply_markup.inline_keyboard[0]
    assert buttons[0].callback_data == f"approve_admin:{request_id}"
    assert buttons[1].callback_data == f"reject_admin:{request_id}"


def test_admin_login_button_flow(monkeypatch):
    message = DummyMessage(user_id=101, username="button_user")
    state = DummyFSMContext()

    monkeypatch.setattr(login, "ADMIN_LOGIN_PASSWORD", "BUTTON")
    monkeypatch.setattr(login, "ROOT_ADMIN_ID", 1234)

    sessions = [
        DummySession([None]),  # is_admin check during code validation
        DummySession([None]),  # pending request check
    ]

    factory = make_session_factory(sessions)

    class AsyncSessionWrapper:
        def __init__(self, session):
            self._session = session

        async def __aenter__(self):
            return await self._session.__aenter__()

        async def __aexit__(self, exc_type, exc, tb):
            return await self._session.__aexit__(exc_type, exc, tb)

    def async_session_stub():
        session = factory()
        return AsyncSessionWrapper(session)

    monkeypatch.setattr(login, "async_session", async_session_stub)

    asyncio.run(login.admin_login_prompt(message, state))

    assert message.replies
    prompt_text, _ = message.replies[-1]
    assert "Введите секретный код" in prompt_text
    assert asyncio.run(state.get_state()) == AdminLoginState.waiting_for_code.state

    message.text = "BUTTON"

    asyncio.run(login.admin_login_code_input(message, state))

    assert asyncio.run(state.get_state()) is None
    created_request = sessions[1].added[0]
    assert isinstance(created_request, AdminRequest)
    request_id = created_request.request_id
    assert request_id

    assert any("Запрос отправлен" in text for text, _ in message.replies)
    assert message.bot.sent_messages
    args, kwargs = message.bot.sent_messages[0]
    assert args[0] == 1234
    assert request_id in args[1]
    reply_markup = kwargs.get("reply_markup")
    assert reply_markup is not None
    buttons = reply_markup.inline_keyboard[0]
    assert buttons[0].callback_data == f"approve_admin:{request_id}"
    assert buttons[1].callback_data == f"reject_admin:{request_id}"


def test_promo_without_code(monkeypatch):
    message = DummyMessage()
    command = CommandObject(command="promo", args=None)
    state = DummyFSMContext()

    asyncio.run(promo.activate_promo(message, command, state))

    assert message.replies
    assert message.replies[0][0].startswith("Введите код прямо в чат")
    assert asyncio.run(state.get_state()) == PromoInputState.waiting_for_code.state


def test_promo_with_valid_code(monkeypatch):
    message = DummyMessage(user_id=7, username="player")
    command = CommandObject(command="promo", args="promo2024")
    state = DummyFSMContext()

    monkeypatch.setattr(promo, "ROOT_ADMIN_ID", 555)

    promo_obj = SimpleNamespace(
        id=1,
        code="PROMO2024",
        active=True,
        max_uses=0,
        uses=0,
        reward_type="nuts",
        reward_amount=100,
        value="100",
        promo_type="money",
        expires_at=None,
    )
    user_obj = SimpleNamespace(id=10, tg_id=7, balance=0)

    sessions = [
        DummySession([promo_obj, user_obj, None])
    ]

    factory = make_session_factory(sessions)

    class AsyncSessionWrapper:
        def __init__(self, session):
            self._session = session

        async def __aenter__(self):
            return await self._session.__aenter__()

        async def __aexit__(self, exc_type, exc, tb):
            return await self._session.__aexit__(exc_type, exc, tb)

    def async_session_stub():
        session = factory()
        return AsyncSessionWrapper(session)

    monkeypatch.setattr(promo, "async_session", async_session_stub)

    check_achievements_mock = AsyncMock()
    monkeypatch.setattr(promo, "check_achievements", check_achievements_mock)

    asyncio.run(promo.activate_promo(message, command, state))

    assert promo_obj.uses == 1
    assert user_obj.balance == 100
    assert sessions[0].committed is True
    assert any("Промокод активирован" in text for text, _ in message.replies)
    assert message.bot.sent_messages
    check_achievements_mock.assert_awaited_once_with(user_obj)


class DummyCallbackMessage:
    def __init__(self):
        self.edits = []

    async def edit_text(self, text: str, **kwargs):
        self.edits.append((text, kwargs))


class DummyCallbackQuery:
    def __init__(self, data: str, from_user_id: int = 999):
        self.data = data
        self.from_user = SimpleNamespace(id=from_user_id)
        self.message = DummyCallbackMessage()
        self.bot = DummyBot()
        self.answered = False
        self.answer_kwargs: dict | None = None

    async def answer(self, text: str | None = None, show_alert: bool = False):
        self.answered = True
        self.answer_kwargs = {"text": text, "show_alert": show_alert}


def test_admin_request_callback_approves(monkeypatch):
    monkeypatch.setattr(login, "ROOT_ADMIN_ID", 999)

    request = SimpleNamespace(
        telegram_id=42,
        status="pending",
        username="tester",
        request_id="req-123",
    )

    sessions = [
        DummySession([request]),
    ]

    factory = make_session_factory(sessions)

    class AsyncSessionWrapper:
        def __init__(self, session):
            self._session = session

        async def __aenter__(self):
            return await self._session.__aenter__()

        async def __aexit__(self, exc_type, exc, tb):
            return await self._session.__aexit__(exc_type, exc, tb)

    def async_session_stub():
        session = factory()
        return AsyncSessionWrapper(session)

    monkeypatch.setattr(login, "async_session", async_session_stub)

    call = DummyCallbackQuery("approve_admin:req-123")

    asyncio.run(login.admin_request_callback(call))

    assert request.status == "approved"
    assert sessions[0].committed is True
    assert call.bot.sent_messages
    user_message = call.bot.sent_messages[0]
    assert user_message[0][0] == 42
    assert "одобрена" in user_message[0][1]
    root_notification = call.bot.sent_messages[1]
    assert root_notification[0][0] == 999
    assert "req-123" in root_notification[0][1]
    assert call.message.edits
    assert call.answered is True


def test_admin_request_callback_rejects(monkeypatch):
    monkeypatch.setattr(login, "ROOT_ADMIN_ID", 999)

    request = SimpleNamespace(
        telegram_id=77,
        status="pending",
        username="another",
        request_id="req-999",
    )

    sessions = [
        DummySession([request]),
    ]

    factory = make_session_factory(sessions)

    class AsyncSessionWrapper:
        def __init__(self, session):
            self._session = session

        async def __aenter__(self):
            return await self._session.__aenter__()

        async def __aexit__(self, exc_type, exc, tb):
            return await self._session.__aexit__(exc_type, exc, tb)

    def async_session_stub():
        session = factory()
        return AsyncSessionWrapper(session)

    monkeypatch.setattr(login, "async_session", async_session_stub)

    call = DummyCallbackQuery("reject_admin:req-999")

    asyncio.run(login.admin_request_callback(call))

    assert request.status == "denied"
    assert sessions[0].committed is True
    assert call.bot.sent_messages
    user_message = call.bot.sent_messages[0]
    assert user_message[0][0] == 77
    assert "отказано" in user_message[0][1]
    root_notification = call.bot.sent_messages[1]
    assert root_notification[0][0] == 999
    assert "req-999" in root_notification[0][1]
    assert call.message.edits
    assert call.answered is True