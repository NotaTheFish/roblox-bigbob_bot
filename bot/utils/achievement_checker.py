from __future__ import annotations

from sqlalchemy import select

from bot.db import Achievement, User, UserAchievement, async_session


async def check_achievements(user: User) -> None:
    async with async_session() as session:
        db_user = await session.scalar(select(User).where(User.tg_id == user.tg_id))
        if not db_user:
            return

        owned_result = await session.scalars(
            select(UserAchievement.achievement_id).where(
                UserAchievement.tg_id == db_user.tg_id
            )
        )
        owned = set(owned_result.all())

        all_achievements_result = await session.scalars(select(Achievement))
        all_achievements = all_achievements_result.all()

        granted = False
        for achievement in all_achievements:
            if achievement.id in owned:
                continue

            # Начало игры
            if achievement.name == "Начало игры":
                session.add(
                    UserAchievement(
                        tg_id=db_user.tg_id,
                        user_id=db_user.id,
                        achievement_id=achievement.id,
                    )
                )
                db_user.balance += achievement.reward
                granted = True

            # Первый донат
            elif achievement.name == "Первый донат" and db_user.balance >= 100:
                session.add(
                    UserAchievement(
                        tg_id=db_user.tg_id,
                        user_id=db_user.id,
                        achievement_id=achievement.id,
                    )
                )
                db_user.balance += achievement.reward
                granted = True

            # Магнат
            elif achievement.name == "Магнат" and db_user.balance >= 10000:
                session.add(
                    UserAchievement(
                        tg_id=db_user.tg_id,
                        user_id=db_user.id,
                        achievement_id=achievement.id,
                    )
                )
                db_user.balance += achievement.reward
                granted = True

        if granted:
            await session.commit()
