"""Utilities for working with statistical leaderboards."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, Sequence

from sqlalchemy import select

from bot.db import User, async_session


_CACHE_TTL_SECONDS = 60.0


@dataclass(frozen=True)
class TopUserEntry:
    """A lightweight representation of a leaderboard user."""

    user_id: int
    username: str | None
    tg_username: str | None
    balance: int
    bot_nickname: str | None = None


class _TopUsersCache:
    """In-memory cache for leaderboard results."""

    def __init__(self) -> None:
        self._data: dict[int, tuple[float, list[TopUserEntry]]] = {}
        self._lock = asyncio.Lock()

    async def get(
        self, limit: int, loader: Callable[[], Awaitable[list[TopUserEntry]]]
    ) -> list[TopUserEntry]:
        now = time.monotonic()
        cached = self._data.get(limit)
        if cached and now - cached[0] < _CACHE_TTL_SECONDS:
            return cached[1]

        async with self._lock:
            cached = self._data.get(limit)
            if cached and time.monotonic() - cached[0] < _CACHE_TTL_SECONDS:
                return cached[1]

            entries = await loader()
            self._data[limit] = (time.monotonic(), entries)
            return entries

    def invalidate(self) -> None:
        self._data.clear()


_top_users_cache = _TopUsersCache()


async def get_top_users(limit: int = 50) -> list[TopUserEntry]:
    """Return top users sorted by nuts balance with simple caching."""

    async def _load() -> list[TopUserEntry]:
        async with async_session() as session:
            result = await session.execute(
                select(
                    User.id,
                    User.username,
                    User.tg_username,
                    User.nuts_balance,
                    User.bot_nickname,
                )
                .order_by(User.nuts_balance.desc())
                .limit(limit)
            )
            rows = result.all()

        return [
            TopUserEntry(
                user_id=row.id,
                username=row.username,
                tg_username=row.tg_username,
                balance=row.nuts_balance or 0,
                bot_nickname=row.bot_nickname,
            )
            for row in rows
        ]

    return await _top_users_cache.get(limit, _load)


def format_top_users(entries: Sequence[TopUserEntry]) -> str:
    """Format leaderboard entries for messaging."""

    if not entries:
        return "🏆 Топ игроков: пока нет данных"

    lines = ["🏆 Топ игроков:", ""]
    for position, entry in enumerate(entries, start=1):
        name = _display_name(entry)
        lines.append(f"{position}. {name} — {entry.balance} 🥜")

    return "\n".join(lines)


def _display_name(entry: TopUserEntry) -> str:
    if entry.bot_nickname:
        return entry.bot_nickname
    if entry.username:
        return entry.username
    if entry.tg_username:
        return f"@{entry.tg_username}"
    return f"ID {entry.user_id}"


def invalidate_top_users_cache() -> None:
    """Clear cached leaderboard data."""

    _top_users_cache.invalidate()


__all__ = [
    "TopUserEntry",
    "format_top_users",
    "get_top_users",
    "invalidate_top_users_cache",
]