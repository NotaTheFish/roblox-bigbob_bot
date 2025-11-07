from __future__ import annotations

import pytest

from bot.services import servers as servers_service
from db.models import SERVER_DEFAULT_CLOSED_MESSAGE, Server
from tests.conftest import FakeAsyncSession, make_async_session_stub


def _make_server(server_id: int, *, url: str | None = None, closed: str | None = None) -> Server:
    server = Server(name=f"Server {server_id}", slug=f"server-{server_id}")
    server.id = server_id
    server.url = url
    server.closed_message = closed
    return server


@pytest.mark.anyio("asyncio")
async def test_get_ordered_servers_returns_sorted(monkeypatch):
    server_two = _make_server(2, url="https://two.example", closed="Закрыто")
    server_one = _make_server(1, closed=None)

    session = FakeAsyncSession(scalars_results=[[server_two, server_one]])
    monkeypatch.setattr(
        servers_service, "async_session", make_async_session_stub(session)
    )

    result = await servers_service.get_ordered_servers()

    assert [entry.id for entry in result] == [1, 2]
    assert result[0].url is None
    assert result[1].url == "https://two.example"
    assert result[1].closed_message == "Закрыто"


@pytest.mark.anyio("asyncio")
async def test_get_server_by_id_returns_closed_message(monkeypatch):
    server = _make_server(5, url=None, closed=SERVER_DEFAULT_CLOSED_MESSAGE)

    session = FakeAsyncSession(get_results=[server])
    monkeypatch.setattr(
        servers_service, "async_session", make_async_session_stub(session)
    )

    result = await servers_service.get_server_by_id(5)

    assert result is not None
    assert result.id == 5
    assert result.closed_message == SERVER_DEFAULT_CLOSED_MESSAGE


@pytest.mark.anyio("asyncio")
async def test_get_server_by_id_handles_missing(monkeypatch):
    session = FakeAsyncSession(get_results=[None])
    monkeypatch.setattr(
        servers_service, "async_session", make_async_session_stub(session)
    )

    result = await servers_service.get_server_by_id(123)

    assert result is None