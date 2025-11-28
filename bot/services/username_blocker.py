"""Background enforcement for users without a Telegram username."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.constants.users import DEFAULT_TG_USERNAME
from bot.db import LogEntry, User, async_session
from bot.services.user_blocking import block_user

logger = logging.getLogger(__name__)

ACCOUNT_AGE_THRESHOLD = timedelta(hours=2)
DEFAULT_POLL_INTERVAL_SECONDS = 300
MISSING_USERNAME_REASON = "без username"
MISSING_USERNAME_EVENT = "security.missing_username_block"


def _now(value: datetime | None = None) -> datetime:
    return value or datetime.now(timezone.utc)


def _should_block_user(user: User, *, now: datetime) -> bool:
    if user.tg_username != DEFAULT_TG_USERNAME:
        return False
    if getattr(user, "verified", False):
        return False
    if not user.created_at:
        return False

    return user.created_at <= now - ACCOUNT_AGE_THRESHOLD


async def _load_candidates(session: AsyncSession, *, now: datetime) -> list[User]:
    cutoff = now - ACCOUNT_AGE_THRESHOLD
    stmt = select(User).where(
        User.tg_username == DEFAULT_TG_USERNAME,
        User.verified.is_(False),
        User.created_at <= cutoff,
    )
    result = await session.scalars(stmt)
    return list(result.all())


async def _log_block(session: AsyncSession, user: User) -> None:
    session.add(
        LogEntry(
            event_type=MISSING_USERNAME_EVENT,
            message="Пользователь заблокирован из-за отсутствия username",
            telegram_id=user.tg_id,
            user_id=user.id,
            data={
                "reason": MISSING_USERNAME_REASON,
                "created_at": user.created_at.isoformat() if user.created_at else None,
            },
        )
    )
    await session.commit()


async def enforce_missing_username_block(session: AsyncSession, *, now: datetime | None = None) -> int:
    """Block users without a Telegram username who have not verified within 2 hours."""

    current_time = _now(now)
    candidates = await _load_candidates(session, now=current_time)

    blocked = 0
    for user in candidates:
        if not _should_block_user(user, now=current_time):
            continue

        await block_user(
            session,
            user=user,
            operator_admin=None,
            reason=MISSING_USERNAME_REASON,
        )
        await _log_block(session, user)
        blocked += 1

    return blocked


async def username_blocking_loop(
    stop_event: asyncio.Event, *, interval_seconds: int = DEFAULT_POLL_INTERVAL_SECONDS
) -> None:
    """Periodically enforce username requirements until ``stop_event`` is set."""

    logger.info(
        "Starting username blocking loop (interval=%ss)",
        interval_seconds,
    )
    while not stop_event.is_set():
        try:
            async with async_session() as session:
                await enforce_missing_username_block(session)
        except Exception:
            logger.exception("Username blocking cycle failed")

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            continue


__all__ = [
    "ACCOUNT_AGE_THRESHOLD",
    "DEFAULT_POLL_INTERVAL_SECONDS",
    "MISSING_USERNAME_EVENT",
    "MISSING_USERNAME_REASON",
    "enforce_missing_username_block",
    "username_blocking_loop",
]