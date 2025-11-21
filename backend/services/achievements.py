"""Background helpers for recalculating and granting achievements.

This module centralises achievement evaluation so that it can be triggered both
periodically and in reaction to user-facing events such as payments,
purchases, referrals or progress updates arriving from Roblox/Firebase.
"""
from __future__ import annotations

import asyncio
from typing import Any, Mapping

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import (
    Achievement,
    AchievementConditionType,
    GameProgress,
    LogEntry,
    Payment,
    PromocodeRedemption,
    Product,
    Purchase,
    Referral,
    User,
    UserAchievement,
)

from ..config import get_settings
from ..database import session_scope
from ..logging import get_logger
from .nuts import add_nuts

logger = get_logger(__name__)

ACHIEVEMENT_DATA_SOURCES: Mapping[str, str] = {
    "balance": "internal:db.users.balance",
    "nuts": "internal:db.users.nuts_balance",
    "payments": "internal:services.payments",
    "purchases": "internal:services.purchases",
    "referrals": "internal:services.referrals",
    "promocodes": "internal:services.promocodes",
    "playtime": "firebase:game_progress",
    "messages": "internal:bot.messages",
}


async def evaluate_and_grant_achievements(
    session: AsyncSession,
    *,
    user: User,
    trigger: str,
    payload: Mapping[str, Any] | None = None,
) -> list[UserAchievement]:
    """Recalculate user progress and grant achievements when thresholds are met."""

    owned_result = await session.scalars(
        select(UserAchievement.achievement_id).where(UserAchievement.tg_id == user.tg_id)
    )
    owned = set(owned_result.all())

    all_achievements = (await session.scalars(select(Achievement))).all()
    granted: list[UserAchievement] = []

    for achievement in all_achievements:
        if achievement.id in owned or achievement.manual_grant_only:
            continue

        condition_met, condition_details = await _check_condition(session, achievement, user)
        if not condition_met:
            continue

        achievement_entry = UserAchievement(
            tg_id=user.tg_id,
            user_id=user.id,
            achievement_id=achievement.id,
            metadata_json={
                "trigger": trigger,
                "payload": dict(payload or {}),
                "data_sources": condition_details.get("data_sources", []),
                "observed": condition_details.get("observed"),
                "threshold": condition_details.get("threshold"),
            },
        )
        session.add(achievement_entry)

        await add_nuts(
            session,
            user=user,
            amount=achievement.reward,
            source="achievement",
            transaction_type="achievement",
            reason=achievement.name,
            metadata={"achievement_id": achievement.id, "trigger": trigger},
        )

        log_payload = {
            "achievement_id": achievement.id,
            "trigger": trigger,
            "data_sources": condition_details.get("data_sources"),
            "observed": condition_details.get("observed"),
            "threshold": condition_details.get("threshold"),
            "payload": dict(payload or {}),
        }
        session.add(
            LogEntry(
                user_id=user.id,
                telegram_id=user.tg_id,
                event_type="achievement_granted",
                message=f"Достижение {achievement.name}",
                data=log_payload,
            )
        )

        logger.info(
            "Achievement granted",
            extra={
                "user_id": user.id,
                "telegram_id": user.tg_id,
                "achievement_id": achievement.id,
                "trigger": trigger,
                "data_sources": condition_details.get("data_sources"),
                "observed": condition_details.get("observed"),
                "threshold": condition_details.get("threshold"),
            },
        )

        granted.append(achievement_entry)

    return granted


async def evaluate_user_by_id(
    *,
    session: AsyncSession,
    user_id: int | None = None,
    telegram_id: int | None = None,
    trigger: str,
    payload: Mapping[str, Any] | None = None,
) -> list[UserAchievement]:
    """Convenience wrapper to locate user and call evaluation."""

    stmt = select(User)
    if user_id is not None:
        stmt = stmt.where(User.id == user_id)
    elif telegram_id is not None:
        stmt = stmt.where(User.tg_id == telegram_id)
    else:
        raise ValueError("user_id or telegram_id is required for achievement evaluation")

    user = await session.scalar(stmt)
    if not user:
        logger.info(
            "Achievement evaluation skipped - user missing",
            extra={"user_id": user_id, "telegram_id": telegram_id, "trigger": trigger},
        )
        return []

    return await evaluate_and_grant_achievements(session, user=user, trigger=trigger, payload=payload)


async def run_periodic_recalculation(stop_event: asyncio.Event | None = None) -> None:
    """Background loop to periodically recompute achievements for all users."""

    interval = get_settings().achievements_recalc_interval_seconds
    logger.info(
        "Starting periodic achievement recalculation",
        extra={"interval_seconds": interval, "data_sources": ACHIEVEMENT_DATA_SOURCES},
    )

    while True:
        if stop_event is not None and stop_event.is_set():
            logger.info("Periodic achievement recalculation stopping")
            return

        try:
            async with session_scope() as session:
                user_ids = await session.scalars(select(User.id))
                for user_id in user_ids:
                    await evaluate_user_by_id(
                        session=session,
                        user_id=user_id,
                        trigger="scheduled",
                        payload={"data_sources": ACHIEVEMENT_DATA_SOURCES},
                    )
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Periodic achievement recalculation failed")

        await asyncio.sleep(interval)


async def _check_condition(
    session: AsyncSession, achievement: Achievement, user: User
) -> tuple[bool, Mapping[str, Any]]:
    condition_type = achievement.condition_type or AchievementConditionType.NONE
    if isinstance(condition_type, str):
        try:
            condition_type = AchievementConditionType(condition_type)
        except ValueError:
            return False, {"data_sources": []}

    if condition_type is AchievementConditionType.NONE:
        return True, {"data_sources": [ACHIEVEMENT_DATA_SOURCES["balance"]]}

    if condition_type is AchievementConditionType.FIRST_MESSAGE_SENT:
        has_message = bool(
            await session.scalar(
                select(LogEntry.id)
                .where(
                    LogEntry.user_id == user.id,
                    LogEntry.event_type == "user_message_seen",
                )
                .limit(1)
            )
        )
        return has_message, {
            "observed": int(has_message),
            "data_sources": [ACHIEVEMENT_DATA_SOURCES["messages"]],
        }

    if condition_type is AchievementConditionType.BALANCE_AT_LEAST:
        threshold = achievement.condition_threshold or 0
        observed = user.balance or 0
        return (
            observed >= threshold,
            {
                "threshold": threshold,
                "observed": observed,
                "data_sources": [ACHIEVEMENT_DATA_SOURCES["balance"]],
            },
        )

    if condition_type is AchievementConditionType.NUTS_AT_LEAST:
        threshold = achievement.condition_threshold or 0
        observed = user.nuts_balance or 0
        return (
            observed >= threshold,
            {
                "threshold": threshold,
                "observed": observed,
                "data_sources": [ACHIEVEMENT_DATA_SOURCES["nuts"]],
            },
        )

    if condition_type is AchievementConditionType.PRODUCT_PURCHASE:
        product_id = achievement.condition_value
        stmt = (
            select(Purchase.id)
            .join(Product, Product.id == Purchase.product_id)
            .where(Purchase.user_id == user.id, Purchase.status == "completed")
            .limit(1)
        )
        if product_id:
            stmt = stmt.where(Product.id == product_id)
        has_purchase = bool(await session.scalar(stmt))
        return has_purchase, {"data_sources": [ACHIEVEMENT_DATA_SOURCES["purchases"]]}

    if condition_type is AchievementConditionType.PURCHASE_COUNT_AT_LEAST:
        threshold = achievement.condition_threshold or 0
        count_stmt = select(func.count(Purchase.id)).where(
            Purchase.user_id == user.id, Purchase.status == "completed"
        )
        total = await session.scalar(count_stmt)
        observed = total or 0
        return (
            observed >= threshold,
            {
                "threshold": threshold,
                "observed": observed,
                "data_sources": [ACHIEVEMENT_DATA_SOURCES["purchases"]],
            },
        )

    if condition_type is AchievementConditionType.PAYMENTS_SUM_AT_LEAST:
        threshold = achievement.condition_threshold or 0
        amount_stmt = select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.user_id == user.id, Payment.status.in_(["applied", "processed"])
        )
        total_amount = await session.scalar(amount_stmt)
        observed = total_amount or 0
        return (
            observed >= threshold,
            {
                "threshold": threshold,
                "observed": observed,
                "data_sources": [ACHIEVEMENT_DATA_SOURCES["payments"]],
            },
        )

    if condition_type is AchievementConditionType.REFERRAL_COUNT_AT_LEAST:
        threshold = achievement.condition_threshold or 0
        referral_stmt = select(func.count(Referral.id)).where(
            Referral.referrer_id == user.id, Referral.confirmed.is_(True)
        )
        total_referrals = await session.scalar(referral_stmt)
        observed = total_referrals or 0
        return (
            observed >= threshold,
            {
                "threshold": threshold,
                "observed": observed,
                "data_sources": [ACHIEVEMENT_DATA_SOURCES["referrals"]],
            },
        )

    if condition_type is AchievementConditionType.TIME_IN_GAME_AT_LEAST:
        threshold = achievement.condition_threshold or 0
        playtime = await _load_playtime_minutes(session, user)
        observed = playtime or 0
        return (
            bool(playtime) and playtime >= threshold,
            {
                "threshold": threshold,
                "observed": observed,
                "data_sources": [ACHIEVEMENT_DATA_SOURCES["playtime"]],
            },
        )

    if condition_type is AchievementConditionType.SPENT_SUM_AT_LEAST:
        threshold = achievement.condition_threshold or 0
        spent_stmt = select(func.coalesce(func.sum(Purchase.total_price), 0)).where(
            Purchase.user_id == user.id, Purchase.status == "completed"
        )
        spent_total = await session.scalar(spent_stmt)
        observed = spent_total or 0
        return (
            observed >= threshold,
            {
                "threshold": threshold,
                "observed": observed,
                "data_sources": [ACHIEVEMENT_DATA_SOURCES["purchases"]],
            },
        )

    if condition_type is AchievementConditionType.PROMOCODE_REDEMPTION_COUNT_AT_LEAST:
        threshold = achievement.condition_threshold or 0
        promo_stmt = select(func.count(PromocodeRedemption.id)).where(
            PromocodeRedemption.user_id == user.id
        )
        promo_total = await session.scalar(promo_stmt)
        observed = promo_total or 0
        return (
            observed >= threshold,
            {
                "threshold": threshold,
                "observed": observed,
                "data_sources": [ACHIEVEMENT_DATA_SOURCES["promocodes"]],
            },
        )

    return False, {"data_sources": []}


async def _load_playtime_minutes(session: AsyncSession, user: User) -> int | None:
    if not user.roblox_id:
        return None

    progress = await session.scalar(
        select(GameProgress.progress)
        .where(GameProgress.roblox_user_id == str(user.roblox_id))
        .order_by(GameProgress.updated_at.desc())
        .limit(1)
    )
    if not isinstance(progress, dict):
        return None

    for key in (
        "time_in_game",
        "timeInGame",
        "play_time",
        "playTime",
        "playtime",
        "minutes_played",
    ):
        value = progress.get(key)
        if isinstance(value, (int, float)):
            return int(value)

    return None


__all__ = [
    "ACHIEVEMENT_DATA_SOURCES",
    "evaluate_and_grant_achievements",
    "evaluate_user_by_id",
    "run_periodic_recalculation",
]