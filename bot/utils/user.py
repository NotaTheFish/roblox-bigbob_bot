"""User-related helper utilities."""

from __future__ import annotations

from typing import Any, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import User, async_session


async def get_user(
    tg_id: int,
    *,
    data: Dict[str, Any] | None = None,
    session: AsyncSession | None = None,
) -> User | None:
    """Fetch a user by Telegram ID with optional context reuse.

    If ``data`` contains ``current_user`` for the same Telegram ID, that value is
    returned without hitting the database. Otherwise, the helper attempts to reuse
    an ``AsyncSession`` provided directly or stored in ``data`` before creating a
    new session on demand. When a user is fetched, it is cached into ``data`` as
    ``current_user`` if the key is not present.
    """

    if data:
        cached_user = data.get("current_user")
        if cached_user and getattr(cached_user, "tg_id", None) == tg_id:
            return cached_user
        if not session:
            session = data.get("session")

    if session:
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
    else:
        async with async_session() as new_session:
            user = await new_session.scalar(select(User).where(User.tg_id == tg_id))

    if data is not None and user and "current_user" not in data:
        data["current_user"] = user

    return user


__all__ = ["get_user"]
