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

from bot.handlers.admin import login
from bot.handlers.user import promo


class DummyBot:
    def __init__(self):
        self.sent_messages = []

    async def send_message(self, *args, **kwargs):
        self.sent_messages.append((args, kwargs))


class DummyMessage:
    def __init__(self, user_id: int = 1, username: str | None = "user"):
        self.from_user = SimpleNamespace(id=user_id, username=username)
        self.bot = DummyBot()
        self.replies: list[tuple[str, dict]] = []

    async def reply(self, text: str, **kwargs):
        self.replies.append((text, kwargs))
        return text


class DummySession:
    def __init__(self, scalar_results: list):
        self._scalar_iter = iter(scalar_results)
        self.added = []
        self.committed = False
        self.flushed = False

    async def scalar(self, *_args, **_kwargs):
        return next(self._scalar_iter, None)

    def add(self, obj):
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
    assert any(
        text.startswith("⌛ Запрос отправлен") for text, _ in message.replies
    )
    assert message.bot.sent_messages


def test_promo_without_code(monkeypatch):
    message = DummyMessage()
    command = CommandObject(command="promo", args=None)

    asyncio.run(promo.activate_promo(message, command))

    assert message.replies
    assert message.replies[0][0].startswith("Введите промокод")


def test_promo_with_valid_code(monkeypatch):
    message = DummyMessage(user_id=7, username="player")
    command = CommandObject(command="promo", args="promo2024")

    monkeypatch.setattr(promo, "ROOT_ADMIN_ID", 555)

    promo_obj = SimpleNamespace(
        id=1,
        code="PROMO2024",
        active=True,
        max_uses=None,
        uses=0,
        promo_type="money",
        reward_amount=100,
        value=None,
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

    asyncio.run(promo.activate_promo(message, command))

    assert promo_obj.uses == 1
    assert user_obj.balance == 100
    assert sessions[0].committed is True
    assert any("Промокод активирован" in text for text, _ in message.replies)
    assert message.bot.sent_messages
    check_achievements_mock.assert_awaited_once_with(user_obj)