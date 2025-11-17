from __future__ import annotations

from sqlalchemy import select

from bot.db import (
    Achievement,
    LogEntry,
    Product,
    Purchase,
    User,
    UserAchievement,
    async_session,
)
from backend.services.nuts import add_nuts


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

            if not await _check_condition(session, achievement, db_user):
                continue

            session.add(
                UserAchievement(
                    tg_id=db_user.tg_id,
                    user_id=db_user.id,
                    achievement_id=achievement.id,
                )
            )
            await add_nuts(
                session,
                user=db_user,
                amount=achievement.reward,
                source="achievement",
                transaction_type="achievement",
                reason=achievement.name,
                metadata={"achievement_id": achievement.id},
            )
            session.add(
                LogEntry(
                    user_id=db_user.id,
                    telegram_id=db_user.tg_id,
                    event_type="achievement_granted",
                    message=f"Достижение {achievement.name}",
                    data={
                        "achievement_id": achievement.id,
                        "reward": achievement.reward,
                        "source": "check_achievements",
                    },
                )
            )
            granted = True

        if granted:
            await session.commit()


async def _check_condition(
    session, achievement: Achievement, user: User
) -> bool:  # pragma: no cover - simple helper
    condition_type = (achievement.condition_type or "none").lower()
    if condition_type == "none":
        return True

    if condition_type == "balance_at_least":
        threshold = achievement.condition_threshold or 0
        return (user.balance or 0) >= threshold

    if condition_type == "nuts_at_least":
        threshold = achievement.condition_threshold or 0
        return (user.nuts_balance or 0) >= threshold

    if condition_type == "product_purchase" and achievement.condition_value:
        stmt = (
            select(Purchase.id)
            .join(Product, Product.id == Purchase.product_id)
            .where(
                Purchase.user_id == user.id,
                Product.slug == achievement.condition_value,
                Purchase.status == "completed",
            )
            .limit(1)
        )
        return bool(await session.scalar(stmt))

    return False
