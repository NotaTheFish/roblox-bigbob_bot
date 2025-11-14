"""Helpers for reading and normalizing user titles."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.sql import Select

from bot.db import User, async_session


@dataclass(frozen=True)
class UserTitleInfo:
    """A compact representation of a user's titles."""

    user_id: int
    telegram_id: int
    titles: list[str]
    selected_title: str | None


def normalize_titles(raw_titles: Any) -> list[str]:
    """Return a cleaned list of unique, non-empty titles."""

    if not isinstance(raw_titles, Sequence) or isinstance(raw_titles, (str, bytes)):
        raw_titles = []

    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw_titles:
        if not isinstance(item, str):
            continue
        cleaned = item.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)

    return normalized


async def get_user_titles_by_tg_id(tg_id: int) -> UserTitleInfo | None:
    """Load titles information for a user via Telegram ID."""

    stmt = _base_query().where(User.tg_id == tg_id)
    return await _fetch_user_titles(stmt)


async def get_user_titles_by_user_id(user_id: int) -> UserTitleInfo | None:
    """Load titles information for a user via primary key ID."""

    stmt = _base_query().where(User.id == user_id)
    return await _fetch_user_titles(stmt)


def _base_query() -> Select:
    return select(
        User.id.label("user_id"),
        User.tg_id.label("telegram_id"),
        User.titles.label("titles"),
        User.selected_title.label("selected_title"),
    ).limit(1)


async def _fetch_user_titles(stmt: Select) -> UserTitleInfo | None:
    async with async_session() as session:
        result = await session.execute(stmt)
        row = result.first()

    if not row:
        return None

    return UserTitleInfo(
        user_id=row.user_id,
        telegram_id=row.telegram_id,
        titles=normalize_titles(row.titles),
        selected_title=row.selected_title,
    )


__all__ = [
    "UserTitleInfo",
    "get_user_titles_by_tg_id",
    "get_user_titles_by_user_id",
    "normalize_titles",
]