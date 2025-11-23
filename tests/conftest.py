"""Shared test fixtures and utilities."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, Iterable, List, Sequence

import pytest


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


os.environ.setdefault("TELEGRAM_TOKEN", "test:token")
os.environ.setdefault("ADMIN_LOGIN_PASSWORD", "DEFAULT")
os.environ.setdefault("ROOT_ADMIN_ID", "0")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")


class MockBot:
    """Minimal async bot stub capturing sent messages."""

    def __init__(self) -> None:
        self.sent_messages: List[tuple[tuple, dict]] = []
        self.invoice_links: List[tuple[tuple, dict]] = []

    async def send_message(self, *args, **kwargs):
        self.sent_messages.append((args, kwargs))

    async def create_invoice_link(self, *args, **kwargs):
        self.invoice_links.append((args, kwargs))
        return f"https://t.me/pay/{len(self.invoice_links)}"


class MockMessage:
    """Simple message stub for handler tests."""

    def __init__(
        self,
        *,
        text: str = "",
        bot: MockBot | None = None,
        user_id: int = 1,
        username: str | None = "user",
        full_name: str = "Test User",
        message_id: int = 1,
    ) -> None:
        self.text = text
        self.bot = bot or MockBot()
        self.from_user = SimpleNamespace(id=user_id, username=username, full_name=full_name)
        self.message_id = message_id
        self.answers: list[tuple[str, dict]] = []
        self.replies: list[tuple[str, dict]] = []

    async def answer(self, text: str, *args, **kwargs):
        if args:
            text = "".join([text, *map(str, args)])
        self.answers.append((text, kwargs))
        return text

    async def reply(self, text: str, **kwargs):
        self.replies.append((text, kwargs))
        return text


class MockCallbackMessage:
    """Stub representing callback query messages."""

    def __init__(self) -> None:
        self.edits: list[tuple[str, dict]] = []
        self.answers: list[tuple[str, dict]] = []

    async def edit_text(self, text: str, **kwargs):
        self.edits.append((text, kwargs))
        return text

    async def answer(self, text: str, **kwargs):
        self.answers.append((text, kwargs))
        return text


class MockCallbackQuery:
    """Callback query stub with answer tracking."""

    def __init__(
        self,
        data: str,
        *,
        bot: MockBot,
        from_user_id: int = 1,
        message: MockCallbackMessage | None = None,
    ) -> None:
        self.data = data
        self.bot = bot
        self.from_user = SimpleNamespace(id=from_user_id)
        self.message = message or MockCallbackMessage()
        self.answers: list[tuple[str | None, bool]] = []

    async def answer(self, text: str | None = None, show_alert: bool = False):
        self.answers.append((text, show_alert))
        return None


class MockFSMContext:
    """In-memory FSM context used across async handler tests."""

    def __init__(self) -> None:
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


class FakeScalarResult:
    def __init__(self, values: Sequence):
        self._values = list(values)

    def all(self):
        return list(self._values)


class FakeExecuteResult:
    def __init__(self, rows: Sequence):
        self._rows = list(rows)

    def all(self):
        return list(self._rows)


class FakeAsyncSession:
    """Lightweight async session mimicking common SQLAlchemy APIs."""

    def __init__(
        self,
        *,
        scalar_results: Iterable | None = None,
        scalars_results: Iterable[Sequence] | None = None,
        get_results: Iterable | None = None,
        execute_results: Iterable[Sequence] | None = None,
    ) -> None:
        self._scalar_results = list(scalar_results or [])
        self._scalars_results = list(scalars_results or [])
        self._get_results = list(get_results or [])
        self._execute_results = list(execute_results or [])
        self.added: list = []
        self.committed = False
        self.flushed = False
        self.execute_calls = 0
        self.deleted: list = []
        self.executed_statements: list = []
        self.rolled_back = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def scalar(self, *_args, **_kwargs):
        if self._scalar_results:
            return self._scalar_results.pop(0)
        return None

    async def scalars(self, *_args, **_kwargs):
        if self._scalars_results:
            values = self._scalars_results.pop(0)
        else:
            values = []
        return FakeScalarResult(values)

    async def get(self, *_args, **_kwargs):
        if self._get_results:
            return self._get_results.pop(0)
        return None

    async def execute(self, *args, **kwargs):
        self.execute_calls += 1
        if args:
            self.executed_statements.append(args[0])
        else:
            self.executed_statements.append(None)
        if self._execute_results:
            rows = self._execute_results.pop(0)
        else:
            rows = []
        return FakeExecuteResult(rows)

    def add(self, obj):
        self.added.append(obj)

    class _BeginContext:
        def __init__(self, session: "FakeAsyncSession") -> None:
            self._session = session

        async def __aenter__(self):
            return self._session

        async def __aexit__(self, exc_type, exc, tb):
            if exc_type:
                self._session.rolled_back = True
            else:
                self._session.committed = True
            return False

    def begin(self):
        return self._BeginContext(self)

    async def delete(self, obj):
        self.deleted.append(obj)

    async def flush(self):
        self.flushed = True
        for idx, obj in enumerate(self.added, start=1):
            if hasattr(obj, "id") and getattr(obj, "id", None) is None:
                setattr(obj, "id", idx)
            if hasattr(obj, "request_id") and getattr(obj, "request_id", None) in (None, ""):
                setattr(obj, "request_id", f"req-{idx}")

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True


def make_async_session_stub(*sessions: FakeAsyncSession) -> Callable[[], FakeAsyncSession]:
    """Return a factory producing the provided fake sessions in order."""

    queue = list(sessions)

    def factory() -> FakeAsyncSession:
        if not queue:
            raise RuntimeError("No fake sessions configured")
        return queue.pop(0)

    return factory


@pytest.fixture
async def mock_bot() -> MockBot:
    return MockBot()


@pytest.fixture
async def mock_state() -> MockFSMContext:
    return MockFSMContext()


@pytest.fixture
async def message_factory(mock_bot: MockBot) -> Callable[..., MockMessage]:
    def factory(**kwargs) -> MockMessage:
        kwargs.setdefault("bot", mock_bot)
        return MockMessage(**kwargs)

    return factory


@pytest.fixture
async def callback_query_factory(mock_bot: MockBot) -> Callable[..., MockCallbackQuery]:
    def factory(data: str, **kwargs) -> MockCallbackQuery:
        kwargs.setdefault("bot", mock_bot)
        return MockCallbackQuery(data, **kwargs)

    return factory


@pytest.fixture
def anyio_backend():  # pragma: no cover - configuration hook for anyio plugin
    return "asyncio"


__all__ = [
    "MockBot",
    "MockMessage",
    "MockCallbackMessage",
    "MockCallbackQuery",
    "MockFSMContext",
    "FakeAsyncSession",
    "make_async_session_stub",
]