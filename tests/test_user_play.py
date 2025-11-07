from __future__ import annotations
from unittest.mock import AsyncMock

import pytest
from aiogram.types import InlineKeyboardMarkup

from bot.handlers.user import menu as user_menu
from bot.services.servers import ServerInfo
from db.models import SERVER_DEFAULT_CLOSED_MESSAGE


@pytest.mark.anyio("asyncio")
async def test_open_play_menu_builds_inline_keyboard(monkeypatch, message_factory, mock_state):
    servers = [
        ServerInfo(id=1, name="Сервер 1", url="https://one.example", closed_message=None),
        ServerInfo(id=2, name="Сервер 2", url=None, closed_message="Скоро откроется"),
    ]
    monkeypatch.setattr(
        user_menu,
        "get_ordered_servers",
        AsyncMock(return_value=servers),
    )

    message = message_factory(text="🎮 Играть")
    await user_menu.open_play_menu(message, mock_state)

    assert message.answers
    text, params = message.answers[-1]
    assert "🎮 Выберите сервер" in text

    markup = params.get("reply_markup")
    assert isinstance(markup, InlineKeyboardMarkup)
    assert len(markup.inline_keyboard) == 2
    first_button = markup.inline_keyboard[0][0]
    second_button = markup.inline_keyboard[1][0]

    assert first_button.url == "https://one.example"
    assert first_button.callback_data is None
    assert second_button.url is None
    assert second_button.callback_data == "server_closed:2"


@pytest.mark.anyio("asyncio")
async def test_open_play_menu_handles_empty_list(monkeypatch, message_factory, mock_state):
    monkeypatch.setattr(
        user_menu,
        "get_ordered_servers",
        AsyncMock(return_value=[]),
    )

    message = message_factory(text="🎮 Играть")
    await user_menu.open_play_menu(message, mock_state)

    assert message.answers
    text, _ = message.answers[-1]
    assert "Доступных серверов пока нет" in text


@pytest.mark.anyio("asyncio")
async def test_server_closed_callback_uses_custom_message(monkeypatch, callback_query_factory):
    server = ServerInfo(id=2, name="Сервер 2", url=None, closed_message="Позже")
    monkeypatch.setattr(
        user_menu,
        "get_server_by_id",
        AsyncMock(return_value=server),
    )

    callback = callback_query_factory("server_closed:2")
    await user_menu.handle_server_closed(callback)

    assert callback.answers
    message, show_alert = callback.answers[-1]
    assert message == "Позже"
    assert show_alert is True


@pytest.mark.anyio("asyncio")
async def test_server_closed_callback_fallback(monkeypatch, callback_query_factory):
    monkeypatch.setattr(
        user_menu,
        "get_server_by_id",
        AsyncMock(return_value=None),
    )

    callback = callback_query_factory("server_closed:invalid")
    await user_menu.handle_server_closed(callback)

    assert callback.answers
    message, show_alert = callback.answers[-1]
    assert message == SERVER_DEFAULT_CLOSED_MESSAGE
    assert show_alert is True