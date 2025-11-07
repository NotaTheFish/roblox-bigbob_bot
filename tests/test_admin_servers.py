from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from bot.handlers.admin import servers
from bot.states.server_states import ServerManageState
from db.models import SERVER_DEFAULT_CLOSED_MESSAGE, LogEntry, Server
from tests.conftest import FakeAsyncSession, make_async_session_stub


def _make_server(server_id: int, *, url: str | None = None) -> Server:
    server = Server(name=f"Legacy {server_id}", slug=f"legacy-{server_id}")
    server.id = server_id
    server.url = url
    server.closed_message = SERVER_DEFAULT_CLOSED_MESSAGE
    return server


@pytest.fixture(autouse=True)
def _auto_admin(monkeypatch):
    monkeypatch.setattr(servers, "is_admin", AsyncMock(return_value=True))


@pytest.mark.anyio("asyncio")
async def test_server_create_auto_fields(monkeypatch, message_factory, mock_state):
    existing = _make_server(1, url="https://old.example")
    session = FakeAsyncSession(scalars_results=[[existing]])
    monkeypatch.setattr(servers, "async_session", make_async_session_stub(session))

    message = message_factory(text=servers.SERVER_CREATE_BUTTON)
    await servers.server_create(message, mock_state)

    new_server = next(obj for obj in session.added if isinstance(obj, Server))
    assert new_server.name == "Сервер 2"
    assert new_server.slug == "server-2"
    assert new_server.url is None
    assert new_server.closed_message == SERVER_DEFAULT_CLOSED_MESSAGE

    assert existing.name == "Сервер 1"
    assert existing.slug == "server-1"

    log_entry = next(obj for obj in session.added if isinstance(obj, LogEntry))
    assert log_entry.event_type == "server_created"
    assert session.committed is True

    assert message.answers
    text, params = message.answers[-1]
    assert "Сервер <b>Сервер 2</b> создан" in text
    assert "Slug: <code>server-2</code>" in text
    assert "reply_markup" in params


@pytest.mark.anyio("asyncio")
async def test_server_delete_reindexes(monkeypatch, message_factory, mock_state):
    server1 = _make_server(1)
    server2 = _make_server(2)

    session_list = [
        FakeAsyncSession(scalars_results=[[server1, server2]]),
        FakeAsyncSession(scalars_results=[[server1, server2]]),
    ]
    monkeypatch.setattr(
        servers, "async_session", make_async_session_stub(*session_list)
    )

    message = message_factory(text=servers.SERVER_DELETE_BUTTON)
    await servers.server_delete_start(message, mock_state)

    assert await mock_state.get_state() == ServerManageState.waiting_for_server.state

    delete_message = message_factory(text="1")
    await servers.server_select_handler(delete_message, mock_state)

    delete_session = session_list[1]
    assert delete_session.deleted and delete_session.deleted[0] is server1
    assert server2.name == "Сервер 1"
    assert server2.slug == "server-1"

    log_entry = next(obj for obj in delete_session.added if isinstance(obj, LogEntry))
    assert log_entry.event_type == "server_deleted"
    assert delete_session.committed is True


@pytest.mark.anyio("asyncio")
async def test_server_set_link_updates(monkeypatch, message_factory, mock_state):
    server = _make_server(1)

    session_list = [
        FakeAsyncSession(scalars_results=[[server]]),
        FakeAsyncSession(scalars_results=[[server]]),
    ]
    monkeypatch.setattr(
        servers, "async_session", make_async_session_stub(*session_list)
    )

    message = message_factory(text=servers.SERVER_SET_LINK_BUTTON)
    await servers.server_set_link_start(message, mock_state)

    select_message = message_factory(text="1")
    await servers.server_select_handler(select_message, mock_state)

    assert await mock_state.get_state() == ServerManageState.waiting_for_link.state

    finish_message = message_factory(text="https://new.example")
    await servers.server_set_link_finish(finish_message, mock_state)

    update_session = session_list[1]
    assert server.url == "https://new.example"
    assert server.closed_message == SERVER_DEFAULT_CLOSED_MESSAGE
    assert update_session.committed is True

    log_entry = next(obj for obj in update_session.added if isinstance(obj, LogEntry))
    assert log_entry.event_type == "server_link_updated"


@pytest.mark.anyio("asyncio")
async def test_server_clear_link_requests_message(
    monkeypatch, message_factory, mock_state
):
    server = _make_server(1, url="https://old.example")
    server.closed_message = "Старое сообщение"

    session_list = [
        FakeAsyncSession(scalars_results=[[server]]),
        FakeAsyncSession(scalars_results=[[server]]),
    ]
    monkeypatch.setattr(
        servers, "async_session", make_async_session_stub(*session_list)
    )

    message = message_factory(text=servers.SERVER_CLEAR_LINK_BUTTON)
    await servers.server_clear_link_start(message, mock_state)

    select_message = message_factory(text="1")
    await servers.server_select_handler(select_message, mock_state)

    assert (
        await mock_state.get_state()
        == ServerManageState.waiting_for_closed_message.state
    )

    finish_message = message_factory(text="Новый текст")
    await servers.server_clear_link_finish(finish_message, mock_state)

    clear_session = session_list[1]
    assert server.url is None
    assert server.closed_message == "Новый текст"
    assert clear_session.committed is True

    log_entry = next(obj for obj in clear_session.added if isinstance(obj, LogEntry))
    assert log_entry.event_type == "server_link_removed"