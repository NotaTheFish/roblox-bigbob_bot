"""Background helpers for recalculating and granting achievements.

This module centralises achievement evaluation so that it can be triggered both
periodically and in reaction to user-facing events such as payments,
purchases, referrals or progress updates arriving from Roblox/Firebase.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
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
from .telegram import send_message

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
    "profile": "internal:bot.profile",
}


def _escape_markdown(text: str) -> str:
    """Escape characters that have special meaning in Markdown."""

    markdown_chars = "\\`*_{}[]()#+-.!|>"
    return "".join(f"\\{char}" if char in markdown_chars else char for char in text)


async def notify_user_achievement_granted(*, user: User, achievement: Achievement) -> None:
    """Send a Telegram DM informing the user about a newly granted achievement."""

    if not user.tg_id:
        return

    name = _escape_markdown(achievement.name)
    description = _escape_markdown(achievement.description or "")
    reward = achievement.reward or 0

    lines = [f"🏆 *{name}*"]
    if reward > 0:
        lines.append(f"Награда: {reward}🥜")
    if description:
        lines.append(description)

    await send_message(
        chat_id=user.tg_id,
        text="\n".join(lines),
        parse_mode="Markdown",
    )


def _normalize_product_condition_value(
    raw_value: Any,
) -> tuple[int | None, str | None]:
    """Split product purchase condition into numeric ID or slug."""

    if raw_value is None:
        return None, None

    if isinstance(raw_value, int):
        return raw_value, None

    if isinstance(raw_value, str):
        value = raw_value.strip()
        if not value:
            return None, None
        if value.isdigit():
            return int(value), None
        return None, value

    return None, None


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

        if achievement.condition_type:
            try:
                condition_type = AchievementConditionType(achievement.condition_type)
            except ValueError:
                continue
            if condition_type is AchievementConditionType.SECRET_WORD and trigger != "secret_word":
                # Skip secret word achievements for non-message triggers
                continue

        condition_met, condition_details = await _check_condition(
            session,
            achievement,
            user,
            trigger=trigger,
            payload=payload,
        )
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

        await notify_user_achievement_granted(user=user, achievement=achievement)

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
    session: AsyncSession,
    achievement: Achievement,
    user: User,
    *,
    trigger: str,
    payload: Mapping[str, Any] | None = None,
) -> tuple[bool, Mapping[str, Any]]:
    condition_type = achievement.condition_type or AchievementConditionType.NONE
    if isinstance(condition_type, str):
        try:
            condition_type = AchievementConditionType(condition_type)
        except ValueError:
            return False, {"data_sources": []}

    if condition_type is AchievementConditionType.NONE:
        return True, {"data_sources": [ACHIEVEMENT_DATA_SOURCES["balance"]]}

    if condition_type is AchievementConditionType.SECRET_WORD:
        if trigger != AchievementConditionType.SECRET_WORD.value:
            return False, {"data_sources": [ACHIEVEMENT_DATA_SOURCES["messages"]]}

        message_text: str | None = None
        if isinstance(payload, Mapping):
            raw_message = payload.get("text")
            if isinstance(raw_message, str):
                message_text = raw_message.strip()

        condition_value = achievement.condition_value
        if not message_text or not isinstance(condition_value, str):
            return False, {"data_sources": [ACHIEVEMENT_DATA_SOURCES["messages"]]}

        matches = message_text.lower() == condition_value.strip().lower()
        return matches, {
            "threshold": condition_value,
            "observed": message_text,
            "data_sources": [ACHIEVEMENT_DATA_SOURCES["messages"]],
        }

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
        product_id, product_slug = _normalize_product_condition_value(
            achievement.condition_value
        )
        if achievement.condition_value is not None and not (product_id or product_slug):
            return False, {"data_sources": [ACHIEVEMENT_DATA_SOURCES["purchases"]]}
        stmt = (
            select(Purchase.id)
            .join(Product, Product.id == Purchase.product_id)
            .where(Purchase.user_id == user.id, Purchase.status == "completed")
            .limit(1)
        )
        if product_id is not None:
            stmt = stmt.where(Product.id == product_id)
        elif product_slug:
            stmt = stmt.where(Product.slug == product_slug)
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

    if condition_type is AchievementConditionType.PROFILE_PHRASE_STREAK:
        phrase: str | None = None
        if isinstance(achievement.metadata_json, dict):
            value = achievement.metadata_json.get("phrase")
            if isinstance(value, str):
                phrase = value.strip()

        threshold_hours = achievement.condition_threshold or 0
        if not phrase:
            return False, {"data_sources": [ACHIEVEMENT_DATA_SOURCES["profile"]]}

        about_text = (user.about_text or "").lower()
        phrase_present = phrase.lower() in about_text

        updated_at = user.about_text_updated_at
        if not phrase_present or not updated_at:
            return (
                False,
                {
                    "threshold": threshold_hours,
                    "observed": 0,
                    "data_sources": [ACHIEVEMENT_DATA_SOURCES["profile"]],
                },
            )

        elapsed = datetime.now(timezone.utc) - updated_at
        elapsed_hours = elapsed.total_seconds() / 3600
        meets_threshold = elapsed >= timedelta(hours=threshold_hours)
        return (
            meets_threshold,
            {
                "threshold": threshold_hours,
                "observed": elapsed_hours,
                "data_sources": [ACHIEVEMENT_DATA_SOURCES["profile"]],
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
    "notify_user_achievement_granted",
]