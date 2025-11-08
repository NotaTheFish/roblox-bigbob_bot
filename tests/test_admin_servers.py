from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from bot.handlers.admin import servers
from bot.states.server_states import ServerManageState
from db.models import SERVER_DEFAULT_CLOSED_MESSAGE, LogEntry, Server
from tests.conftest import FakeAsyncSession, make_async_session_stub
from sqlalchemy.exc import IntegrityError


def _make_server(server_id: int, *, url: str | None = None) -> Server:
    server = Server(name=f"Legacy {server_id}", slug=f"legacy-{server_id}")
    server.id = server_id
    server.url = url
    server.closed_message = SERVER_DEFAULT_CLOSED_MESSAGE
    return server


@pytest.fixture(autouse=True)
def _auto_admin(monkeypatch):
    monkeypatch.setattr(servers, "is_admin", AsyncMock(return_value=True))


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("12", 12),
        ("🗑 12", 12),
        ("ID: 12", 12),
        ("server-99", 99),
        ("no digits", None),
        (None, None),
    ],
)
def test_parse_server_id_strips_non_digits(raw, expected):
    assert servers._parse_server_id(raw) == expected


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
    assert log_entry.server_id is None
    assert log_entry.data == {"server_id": 1, "server_name": "Legacy 1"}
    assert delete_session.committed is True

    assert delete_message.answers
    text, params = delete_message.answers[-1]
    assert text == "✅ Сервер успешно удалён"
    assert "reply_markup" in params


@pytest.mark.anyio("asyncio")
async def test_server_create_then_delete(monkeypatch, message_factory, mock_state):
    create_session = FakeAsyncSession(scalars_results=[[]])
    delete_start_session = FakeAsyncSession()
    delete_session = FakeAsyncSession()

    monkeypatch.setattr(
        servers,
        "async_session",
        make_async_session_stub(create_session, delete_start_session, delete_session),
    )

    create_message = message_factory(text=servers.SERVER_CREATE_BUTTON)
    await servers.server_create(create_message, mock_state)

    created_server = next(obj for obj in create_session.added if isinstance(obj, Server))
    created_server.id = 1

    delete_start_session._scalars_results = [[created_server]]
    delete_session._scalars_results = [[created_server]]

    delete_start_message = message_factory(text=servers.SERVER_DELETE_BUTTON)
    await servers.server_delete_start(delete_start_message, mock_state)

    delete_confirm_message = message_factory(text="1")
    await servers.server_select_handler(delete_confirm_message, mock_state)

    delete_log = next(obj for obj in delete_session.added if isinstance(obj, LogEntry))
    assert delete_log.event_type == "server_deleted"
    assert delete_log.server_id is None
    assert delete_log.data == {"server_id": 1, "server_name": created_server.name}

    assert delete_session.deleted and delete_session.deleted[0] is created_server
    assert delete_session.committed is True

    assert delete_confirm_message.answers
    text, params = delete_confirm_message.answers[-1]
    assert text == "✅ Сервер успешно удалён"
    assert "reply_markup" in params


@pytest.mark.anyio("asyncio")
async def test_server_delete_removes_related_data(monkeypatch, message_factory, mock_state):
    server = _make_server(1)

    session_list = [
        FakeAsyncSession(scalars_results=[[server]]),
        FakeAsyncSession(
            scalars_results=[[server], [101, 102], [201]],
            execute_results=[[], [], [], [], [], []],
        ),
    ]
    monkeypatch.setattr(
        servers,
        "async_session",
        make_async_session_stub(*session_list),
    )

    start_message = message_factory(text=servers.SERVER_DELETE_BUTTON)
    await servers.server_delete_start(start_message, mock_state)

    confirm_message = message_factory(text="1")
    await servers.server_select_handler(confirm_message, mock_state)

    delete_session = session_list[1]
    assert delete_session.execute_calls == 6
    table_names = [
        stmt.table.name for stmt in delete_session.executed_statements if stmt is not None
    ]
    assert table_names.count("referral_rewards") == 2
    assert "payment_webhooks" in table_names
    assert "payments" in table_names
    assert "purchases" in table_names
    assert "products" in table_names
    assert delete_session.deleted and delete_session.deleted[0] is server
    assert delete_session.committed is True

    assert confirm_message.answers
    text, params = confirm_message.answers[-1]
    assert text == "✅ Сервер успешно удалён"
    assert "reply_markup" in params


@pytest.mark.anyio("asyncio")
async def test_server_delete_integrity_error(monkeypatch, message_factory, mock_state):
    server = _make_server(1)

    delete_session = FakeAsyncSession(scalars_results=[[server]])
    cleanup_mock = AsyncMock()
    commit_mock = AsyncMock(side_effect=IntegrityError("", "", Exception()))

    monkeypatch.setattr(servers, "_cleanup_server_related_data", cleanup_mock)
    monkeypatch.setattr(delete_session, "commit", commit_mock)

    session_list = [
        FakeAsyncSession(scalars_results=[[server]]),
        delete_session,
    ]
    monkeypatch.setattr(
        servers,
        "async_session",
        make_async_session_stub(*session_list),
    )

    start_message = message_factory(text=servers.SERVER_DELETE_BUTTON)
    await servers.server_delete_start(start_message, mock_state)

    confirm_message = message_factory(text="1")
    await servers.server_select_handler(confirm_message, mock_state)

    assert cleanup_mock.await_count == 1
    assert commit_mock.await_count == 1
    assert delete_session.rolled_back is True

    assert confirm_message.answers
    text, params = confirm_message.answers[-1]
    assert "⚠️ Не удалось удалить сервер" in text
    assert "reply_markup" in params
    assert await mock_state.get_state() is None

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