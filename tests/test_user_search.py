"""Tests for the user search helpers."""

from __future__ import annotations

import pytest

from bot.db import User
from bot.services import user_search
from db.constants import BOT_USER_ID_PREFIX
from tests.conftest import FakeAsyncSession, make_async_session_stub


def _make_user(**overrides) -> User:
    defaults = {
        "bot_user_id": f"{BOT_USER_ID_PREFIX}1",
        "tg_id": 1,
    }
    defaults.update(overrides)
    return User(**defaults)


@pytest.mark.anyio
async def test_find_user_by_query_returns_none_for_blank_input():
    result = await user_search.find_user_by_query("   ")
    assert result is None


@pytest.mark.anyio
async def test_find_user_by_query_prefers_bot_nickname(monkeypatch):
    user = _make_user(bot_nickname="Player")
    sentinel = object()
    session = FakeAsyncSession(scalar_results=[user, sentinel])
    monkeypatch.setattr(user_search, "async_session", make_async_session_stub(session))

    result = await user_search.find_user_by_query("  @player  ")

    assert result is user
    assert session._scalar_results == [sentinel]


@pytest.mark.anyio
async def test_find_user_by_query_checks_tg_username(monkeypatch):
    user = _make_user(tg_username="search_user")
    sentinel = object()
    session = FakeAsyncSession(scalar_results=[None, user, sentinel])
    monkeypatch.setattr(user_search, "async_session", make_async_session_stub(session))

    result = await user_search.find_user_by_query("@SEARCH_USER")

    assert result is user
    assert session._scalar_results == [sentinel]


@pytest.mark.anyio
async def test_find_user_by_query_checks_roblox_username(monkeypatch):
    user = _make_user(username="robloxUser")
    sentinel = object()
    session = FakeAsyncSession(scalar_results=[None, None, user, sentinel])
    monkeypatch.setattr(user_search, "async_session", make_async_session_stub(session))

    result = await user_search.find_user_by_query("robloxuser")

    assert result is user
    assert session._scalar_results == [sentinel]


@pytest.mark.anyio
async def test_find_user_by_query_matches_bot_user_id(monkeypatch):
    user = _make_user()
    sentinel = object()
    session = FakeAsyncSession(scalar_results=[None, None, None, user, sentinel])
    monkeypatch.setattr(user_search, "async_session", make_async_session_stub(session))

    bot_user_id = f"{BOT_USER_ID_PREFIX.lower()}123"
    result = await user_search.find_user_by_query(bot_user_id)

    assert result is user
    assert session._scalar_results == [sentinel]


@pytest.mark.anyio
async def test_find_user_by_query_matches_telegram_id_first(monkeypatch):
    user = _make_user(tg_id=9999)
    sentinel = object()
    session = FakeAsyncSession(scalar_results=[None, None, None, user, sentinel])
    monkeypatch.setattr(user_search, "async_session", make_async_session_stub(session))

    result = await user_search.find_user_by_query(" 9999 ")

    assert result is user
    assert session._scalar_results == [sentinel]


@pytest.mark.anyio
async def test_find_user_by_query_falls_back_to_roblox_id(monkeypatch):
    user = _make_user(roblox_id="123456")
    session = FakeAsyncSession(scalar_results=[None, None, None, None, user])
    monkeypatch.setattr(user_search, "async_session", make_async_session_stub(session))

    result = await user_search.find_user_by_query("123456")

    assert result is user
    assert session._scalar_results == []