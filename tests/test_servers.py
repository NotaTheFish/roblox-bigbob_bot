"""Integration-style tests for server creation and user menu flows."""
from __future__ import annotations

from typing import Callable, Iterable, List

import pytest
from unittest.mock import AsyncMock

from aiogram.types import InlineKeyboardMarkup

from bot.handlers.admin import servers as admin_servers
from bot.handlers.user import menu as user_menu
from bot.services import servers as servers_service
from db.models import SERVER_DEFAULT_CLOSED_MESSAGE, Server
from tests.conftest import FakeAsyncSession, FakeScalarResult


class ServerStore:
    """In-memory collection mimicking persisted server records."""

    def __init__(self, servers: Iterable[Server] | None = None) -> None:
        self._servers: List[Server] = []
        self._next_id = 1
        for server in servers or []:
            self.add(server)

    def add(self, server: Server) -> Server:
        if server.id is None:
            server.id = self._next_id
        self._next_id = max(self._next_id, (server.id or 0) + 1)
        if server not in self._servers:
            self._servers.append(server)
        return server

    def remove(self, server: Server) -> None:
        self._servers = [item for item in self._servers if item is not server]

    def all(self) -> List[Server]:
        return list(sorted(self._servers, key=lambda item: item.id or 0))

    def get(self, server_id: int) -> Server | None:
        for server in self._servers:
            if server.id == server_id:
                return server
        return None


class ServerSession(FakeAsyncSession):
    """Fake async session backed by ``ServerStore``."""

    def __init__(self, store: ServerStore) -> None:
        super().__init__()
        self._store = store

    async def scalars(self, *_args, **_kwargs):  # type: ignore[override]
        return FakeScalarResult(self._store.all())

    async def get(self, model, ident):  # type: ignore[override]
        if model is Server:
            return self._store.get(int(ident))
        return None

    def add(self, obj):  # type: ignore[override]
        super().add(obj)
        if isinstance(obj, Server):
            self._store.add(obj)

    async def delete(self, obj):  # type: ignore[override]
        if isinstance(obj, Server):
            self._store.remove(obj)
        await super().delete(obj)

    async def flush(self):  # type: ignore[override]
        self.flushed = True


def make_server_session_factory(store: ServerStore) -> Callable[[], ServerSession]:
    """Return a factory producing ``ServerSession`` bound to ``store``."""

    def factory() -> ServerSession:
        return ServerSession(store)

    return factory


def make_server(*, name: str, slug: str, url: str | None = None, closed_message: str | None = None) -> Server:
    server = Server(name=name, slug=slug, status="active")
    server.url = url
    server.closed_message = closed_message or SERVER_DEFAULT_CLOSED_MESSAGE
    return server


@pytest.fixture(autouse=True)
def _auto_admin(monkeypatch):
    monkeypatch.setattr(admin_servers, "is_admin", AsyncMock(return_value=True))


@pytest.mark.anyio("asyncio")
async def test_server_creation_and_deletion_reindexes(monkeypatch, message_factory, mock_state):
    store = ServerStore()
    session_factory = make_server_session_factory(store)
    monkeypatch.setattr(admin_servers, "async_session", session_factory)
    monkeypatch.setattr(servers_service, "async_session", session_factory)

    create_message_one = message_factory(text=admin_servers.SERVER_CREATE_BUTTON)
    await admin_servers.server_create(create_message_one, mock_state)

    create_message_two = message_factory(text=admin_servers.SERVER_CREATE_BUTTON)
    await admin_servers.server_create(create_message_two, mock_state)

    all_servers = store.all()
    assert [server.name for server in all_servers] == ["Сервер 1", "Сервер 2"]

    delete_start = message_factory(text=admin_servers.SERVER_DELETE_BUTTON)
    await admin_servers.server_delete_start(delete_start, mock_state)

    first_id = all_servers[0].id
    assert first_id is not None

    delete_select = message_factory(text=str(first_id))
    await admin_servers.server_select_handler(delete_select, mock_state)

    remaining = store.all()
    assert len(remaining) == 1
    assert remaining[0].name == "Сервер 1"
    assert remaining[0].slug == "server-1"


@pytest.mark.anyio("asyncio")
async def test_setting_server_link_updates_user_menu(monkeypatch, message_factory, mock_state):
    store = ServerStore([make_server(name="Legacy", slug="legacy", url=None, closed_message="Прежнее")])
    session_factory = make_server_session_factory(store)
    monkeypatch.setattr(admin_servers, "async_session", session_factory)
    monkeypatch.setattr(servers_service, "async_session", session_factory)

    start_message = message_factory(text=admin_servers.SERVER_SET_LINK_BUTTON)
    await admin_servers.server_set_link_start(start_message, mock_state)

    server_id = store.all()[0].id
    select_message = message_factory(text=str(server_id))
    await admin_servers.server_select_handler(select_message, mock_state)

    finish_message = message_factory(text="https://roblox.example/server")
    await admin_servers.server_set_link_finish(finish_message, mock_state)

    updated = store.get(server_id)
    assert updated is not None
    assert updated.url == "https://roblox.example/server"
    assert updated.closed_message == SERVER_DEFAULT_CLOSED_MESSAGE

    play_message = message_factory(text="🎮 Играть")
    await user_menu.open_play_menu(play_message, mock_state)

    assert play_message.answers
    _, params = play_message.answers[-1]
    keyboard = params.get("reply_markup")
    assert isinstance(keyboard, InlineKeyboardMarkup)
    button = keyboard.inline_keyboard[0][0]
    assert button.url == "https://roblox.example/server"
    assert button.callback_data is None


@pytest.mark.anyio("asyncio")
async def test_clearing_server_link_sets_closed_message(monkeypatch, message_factory, mock_state, callback_query_factory):
    store = ServerStore(
        [
            make_server(
                name="Legacy",
                slug="legacy",
                url="https://roblox.example/server",
                closed_message="Прежнее",
            )
        ]
    )
    session_factory = make_server_session_factory(store)
    monkeypatch.setattr(admin_servers, "async_session", session_factory)
    monkeypatch.setattr(servers_service, "async_session", session_factory)

    start_message = message_factory(text=admin_servers.SERVER_CLEAR_LINK_BUTTON)
    await admin_servers.server_clear_link_start(start_message, mock_state)

    server_id = store.all()[0].id
    select_message = message_factory(text=str(server_id))
    await admin_servers.server_select_handler(select_message, mock_state)

    finish_message = message_factory(text="Сервер временно закрыт")
    await admin_servers.server_clear_link_finish(finish_message, mock_state)

    updated = store.get(server_id)
    assert updated is not None
    assert updated.url is None
    assert updated.closed_message == "Сервер временно закрыт"

    play_message = message_factory(text="🎮 Играть")
    await user_menu.open_play_menu(play_message, mock_state)
    _, params = play_message.answers[-1]
    keyboard = params.get("reply_markup")
    assert isinstance(keyboard, InlineKeyboardMarkup)
    button = keyboard.inline_keyboard[0][0]
    assert button.url is None
    assert button.callback_data == f"server_closed:{server_id}"

    callback = callback_query_factory(f"server_closed:{server_id}")
    await user_menu.handle_server_closed(callback)

    assert callback.answers
    message, show_alert = callback.answers[-1]
    assert message == "Сервер временно закрыт"
    assert show_alert is True