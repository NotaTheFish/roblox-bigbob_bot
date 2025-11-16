"""Utilities for searching and rendering user profiles."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import or_, select
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


async def find_user_by_query(query: str, *, include_blocked: bool = True) -> User | None:
    """Find a user by Telegram ID, bot_user_id or username."""

    normalized = query.strip().lstrip("@")
    if not normalized:
        return None

    stmt = (
        select(User)
        .options(selectinload(User.selected_achievement))
        .limit(1)
    )

    if not include_blocked:
        stmt = stmt.where(User.is_blocked.is_(False))

    maybe_bot_id = normalized.upper()
    is_bot_id_query = maybe_bot_id.startswith(BOT_USER_ID_PREFIX)

    async with async_session() as session:
        if is_bot_id_query:
            bot_id_stmt = stmt.where(User.bot_user_id == maybe_bot_id)
            user = await session.scalar(bot_id_stmt)
            if user:
                return user

        filters = []
        if normalized.isdigit():
            filters.append(User.tg_id == int(normalized))

        like_pattern = f"%{normalized}%"
        filters.append(User.tg_username.ilike(like_pattern))
        filters.append(User.username.ilike(like_pattern))

        return await session.scalar(stmt.where(or_(*filters)))


def render_search_profile(user: User, options: SearchRenderOptions) -> str:
    """Render a user profile for search results."""

    titles = normalize_titles(user.titles)
    return render_profile(
        ProfileView(
            heading=options.heading,
            bot_user_id=user.bot_user_id,
            tg_username=user.tg_username or "",
            tg_id=user.tg_id if options.include_private_fields else None,
            roblox_username=user.username or "",
            roblox_id=user.roblox_id or "",
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