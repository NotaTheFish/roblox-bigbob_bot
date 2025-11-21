from __future__ import annotations

from sqlalchemy import func, select

from bot.db import (
    Achievement,
    AchievementConditionType,
    LogEntry,
    Payment,
    Product,
    Purchase,
    Referral,
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
    if achievement.manual_grant_only:
        return False

    condition_type = achievement.condition_type or AchievementConditionType.NONE
    if isinstance(condition_type, str):
        try:
            condition_type = AchievementConditionType(condition_type)
        except ValueError:
            return False

    if condition_type is AchievementConditionType.NONE:
        return True

    if condition_type is AchievementConditionType.BALANCE_AT_LEAST:
        threshold = achievement.condition_threshold or 0
        return (user.balance or 0) >= threshold

    condition_type is AchievementConditionType.NUTS_AT_LEAST:
        threshold = achievement.condition_threshold or 0
        return (user.nuts_balance or 0) >= threshold

    if condition_type is AchievementConditionType.PRODUCT_PURCHASE:
        product_id = achievement.condition_value
        stmt = (
            select(Purchase.id)
            .join(Product, Product.id == Purchase.product_id)
            .where(
                Purchase.user_id == user.id,
                Purchase.status == "completed",
            )
            .limit(1)
        )
        if product_id:
            stmt = stmt.where(Product.id == product_id)
        return bool(await session.scalar(stmt))

    if condition_type is AchievementConditionType.PURCHASE_COUNT_AT_LEAST:
        threshold = achievement.condition_threshold or 0
        count_stmt = select(func.count(Purchase.id)).where(
            Purchase.user_id == user.id, Purchase.status == "completed"
        )
        total = await session.scalar(count_stmt)
        return (total or 0) >= threshold

    if condition_type is AchievementConditionType.PAYMENTS_SUM_AT_LEAST:
        threshold = achievement.condition_threshold or 0
        amount_stmt = select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.user_id == user.id, Payment.status.in_(["applied", "processed"])
        )
        total_amount = await session.scalar(amount_stmt)
        return (total_amount or 0) >= threshold

    if condition_type is AchievementConditionType.REFERRAL_COUNT_AT_LEAST:
        threshold = achievement.condition_threshold or 0
        referral_stmt = select(func.count(Referral.id)).where(
            Referral.referrer_id == user.id, Referral.confirmed.is_(True)
        )
        total_referrals = await session.scalar(referral_stmt)
        return (total_referrals or 0) >= threshold

    return False
