from __future__ import annotations

from sqlalchemy import select

from bot.db import User, async_session
from backend.services.achievements import evaluate_and_grant_achievements


async def check_achievements(user: User) -> None:
    async with async_session() as session:
        db_user = await session.scalar(select(User).where(User.tg_id == user.tg_id))
        if not db_user:
            return

        granted = await evaluate_and_grant_achievements(
            session, user=db_user, trigger="bot_manual_check"
        )
        if granted:
            await session.commit()
