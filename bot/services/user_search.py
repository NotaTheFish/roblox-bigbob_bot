"""Utilities for searching and rendering user profiles."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from bot.db import User, async_session
from db.constants import BOT_USER_ID_PREFIX
from bot.services.profile_renderer import ProfileView, render_profile
from bot.services.user_titles import normalize_titles


@dataclass(frozen=True)
class SearchRenderOptions:
    """Configuration for rendering search results."""

    heading: str
    include_private_fields: bool = True
    roblox_id: str | None = None


async def find_user_by_query(query: str, *, include_blocked: bool = True) -> User | None:
    """Find a user by nickname, username or identifiers in priority order."""

    normalized = query.strip()
    if not normalized:
        return None

    normalized = normalized.lstrip("@").strip()
    if not normalized:
        return None

    normalized_casefold = normalized.casefold()
    maybe_bot_id = normalized.upper()

    stmt = (
        select(User)
        .options(selectinload(User.selected_achievement))
        .limit(1)
    )

    if not include_blocked:
        stmt = stmt.where(User.is_blocked.is_(False))

    async with async_session() as session:
        for column in (User.bot_nickname, User.tg_username, User.username):
            text_stmt = stmt.where(func.lower(column) == normalized_casefold)
            user = await session.scalar(text_stmt)
            if user:
                return user

        if maybe_bot_id.startswith(BOT_USER_ID_PREFIX):
            bot_id_stmt = stmt.where(User.bot_user_id == maybe_bot_id)
            user = await session.scalar(bot_id_stmt)
            if user:
                return user

        if normalized.isdigit():
            tg_id_stmt = stmt.where(User.tg_id == int(normalized))
            user = await session.scalar(tg_id_stmt)
            if user:
                return user

            roblox_id_stmt = stmt.where(User.roblox_id == normalized)
            user = await session.scalar(roblox_id_stmt)
            if user:
                return user

    return None


def render_search_profile(user: User, options: SearchRenderOptions) -> str:
    """Render a user profile for search results."""

    titles = normalize_titles(user.titles)
    roblox_id = options.roblox_id or user.roblox_id or ""
    return render_profile(
        ProfileView(
            heading=options.heading,
            bot_user_id=user.bot_user_id,
            bot_nickname=user.bot_nickname or "",
            tg_username=user.tg_username or "",
            tg_id=user.tg_id if options.include_private_fields else None,
            roblox_username=user.username or "",
            roblox_id=roblox_id,
            balance=user.nuts_balance,
            titles=titles,
            selected_title=user.selected_title,
            selected_achievement=(
                user.selected_achievement.name if user.selected_achievement else None
            ),
            about_text=user.about_text,
            created_at=user.created_at if options.include_private_fields else None,
        )
    )


__all__ = ["SearchRenderOptions", "find_user_by_query", "render_search_profile"]