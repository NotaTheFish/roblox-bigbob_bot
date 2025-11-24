"""Middleware to throttle spammy users and duplicate callbacks."""
from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Deque, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update
from sqlalchemy import select

from bot.config import ADMIN_ROOT_IDS, ADMINS, ROOT_ADMIN_ID
from bot.db import LogEntry, User, async_session
from bot.services.user_blocking import block_user

TelegramHandler = Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]]

logger = logging.getLogger(__name__)

# === Rate limit configuration =============================================
CALLBACK_DUPLICATE_WINDOW_SECONDS = 0.75
WARNING_COOLDOWN_SECONDS = 30.0
FLOOD_BAN_SECONDS = 120.0
FLOOD_BAN_DURATION = timedelta(hours=1)
NEW_USER_AGE_SECONDS = 60 * 60 * 24
ADMIN_LIMIT_BOOST = 3.0

DEFAULT_MESSAGE_LIMIT = (12, 18, 10.0)  # soft, hard, window seconds
DEFAULT_CALLBACK_LIMIT = (18, 28, 10.0)

NEW_USER_MESSAGE_LIMIT = (6, 12, 12.0)
NEW_USER_CALLBACK_LIMIT = (10, 18, 12.0)


@dataclass
class RateLimit:
    soft_limit: int
    hard_limit: int
    window_seconds: float

    def clone_scaled(self, factor: float) -> "RateLimit":
        return RateLimit(
            soft_limit=int(self.soft_limit * factor),
            hard_limit=int(self.hard_limit * factor),
            window_seconds=self.window_seconds,
        )


@dataclass
class UserLimits:
    message: RateLimit
    callback: RateLimit
    duplicate_window_seconds: float = CALLBACK_DUPLICATE_WINDOW_SECONDS
    disabled: bool = False


DEFAULT_LIMITS = UserLimits(
    message=RateLimit(*DEFAULT_MESSAGE_LIMIT),
    callback=RateLimit(*DEFAULT_CALLBACK_LIMIT),
)

NEW_USER_LIMITS = UserLimits(
    message=RateLimit(*NEW_USER_MESSAGE_LIMIT),
    callback=RateLimit(*NEW_USER_CALLBACK_LIMIT),
)


async def get_user_limits(user: User | None, *, from_user_id: int | None = None) -> UserLimits:
    """Return per-user rate limits with admin/owner relaxations."""

    if from_user_id in {ROOT_ADMIN_ID, *ADMIN_ROOT_IDS}:
        return UserLimits(
            message=RateLimit(*DEFAULT_MESSAGE_LIMIT),
            callback=RateLimit(*DEFAULT_CALLBACK_LIMIT),
            duplicate_window_seconds=CALLBACK_DUPLICATE_WINDOW_SECONDS,
            disabled=True,
        )

    if user and user.created_at:
        age_seconds = (datetime.now(timezone.utc) - user.created_at).total_seconds()
        if age_seconds <= NEW_USER_AGE_SECONDS:
            limits = NEW_USER_LIMITS
        else:
            limits = DEFAULT_LIMITS
    else:
        limits = DEFAULT_LIMITS

    if from_user_id in ADMINS:
        return UserLimits(
            message=limits.message.clone_scaled(ADMIN_LIMIT_BOOST),
            callback=limits.callback.clone_scaled(ADMIN_LIMIT_BOOST),
            duplicate_window_seconds=limits.duplicate_window_seconds,
            disabled=False,
        )

    return limits


class AntiSpamMiddleware(BaseMiddleware):
    """Throttle abusive users and suppress duplicate callbacks."""

    def __init__(self) -> None:
        super().__init__()
        self._message_events: Dict[int, Deque[float]] = defaultdict(deque)
        self._callback_events: Dict[int, Deque[float]] = defaultdict(deque)
        self._callback_fingerprints: Dict[int, Dict[str, float]] = defaultdict(dict)
        self._last_warning_at: Dict[int, float] = {}
        self._flood_banned_until: Dict[int, float] = {}
        self._last_callback_data: Dict[int, tuple[str, float]] = {}

    async def _log_security_event(
        self,
        *,
        db_user: User | None,
        telegram_id: int,
        event_type: str,
        message: str,
        data: dict[str, object] | None = None,
    ) -> None:
        try:
            async with async_session() as session:
                session.add(
                    LogEntry(
                        user_id=db_user.id if db_user else None,
                        telegram_id=telegram_id,
                        event_type=event_type,
                        message=message,
                        data=data,
                    )
                )
                await session.commit()
        except Exception:
            logger.debug("Failed to create security log entry", exc_info=True)

    async def __call__(
        self,
        handler: TelegramHandler,
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        try:
            from_user = self._extract_from_user(event)
            user_id = from_user.id if from_user else None
            current_user: User | None = data.get("current_user")

            if user_id is None:
                return await handler(event, data)

            limits = await get_user_limits(current_user, from_user_id=user_id)
            now = time.monotonic()

            # Hard flood ban already in place
            if self._is_flood_banned(user_id, now):
                await self._warn_user(event, user_id, callback_hint=True)
                return None

            # --- CALLBACKS --------------------------------------------------
            if isinstance(event, CallbackQuery):
                is_duplicate, last_seen = self._is_duplicate_callback(
                    event, user_id, limits, now
                )
                if is_duplicate:
                    await self._warn_duplicate_callback(event)
                    await self._log_security_event(
                        db_user=current_user,
                        telegram_id=user_id,
                        event_type="duplicate_callback",
                        message="Duplicate callback suppressed",
                        data={
                            "data": event.data,
                            "window_seconds": limits.duplicate_window_seconds,
                            "last_seen_at": last_seen,
                        },
                    )
                    return None

                if not limits.disabled:
                    decision = self._check_and_record(
                        user_id, now, limits.callback, self._callback_events
                    )
                    if decision == "hard":
                        await self._log_security_event(
                            db_user=current_user,
                            telegram_id=user_id,
                            event_type="hard_flood_callback",
                            message="Callback hard flood limit reached",
                            data={
                                "count": len(self._callback_events[user_id]),
                                "hard_limit": limits.callback.hard_limit,
                                "window_seconds": limits.callback.window_seconds,
                            },
                        )
                        await self._apply_hard_limit(user_id, current_user, now, event)
                        await self._warn_user(event, user_id, callback_hint=True)
                        return None

                    if decision == "soft":
                        await self._log_security_event(
                            db_user=current_user,
                            telegram_id=user_id,
                            event_type="soft_flood_callback",
                            message="Callback soft flood limit reached",
                            data={
                                "count": len(self._callback_events[user_id]),
                                "soft_limit": limits.callback.soft_limit,
                                "window_seconds": limits.callback.window_seconds,
                            },
                        )
                        await self._warn_user(event, user_id, callback_hint=True)
                        return None

                return await handler(event, data)

            # --- MESSAGES --------------------------------------------------
            if isinstance(event, Message):
                if not limits.disabled:
                    decision = self._check_and_record(
                        user_id, now, limits.message, self._message_events
                    )
                    if decision == "hard":
                        await self._log_security_event(
                            db_user=current_user,
                            telegram_id=user_id,
                            event_type="hard_flood_message",
                            message="Message hard flood limit reached",
                            data={
                                "count": len(self._message_events[user_id]),
                                "hard_limit": limits.message.hard_limit,
                                "window_seconds": limits.message.window_seconds,
                            },
                        )
                        await self._apply_hard_limit(user_id, current_user, now, event)
                        await self._warn_user(event, user_id, callback_hint=False)
                        return None

                    if decision == "soft":
                        await self._log_security_event(
                            db_user=current_user,
                            telegram_id=user_id,
                            event_type="soft_flood_message",
                            message="Message soft flood limit reached",
                            data={
                                "count": len(self._message_events[user_id]),
                                "soft_limit": limits.message.soft_limit,
                                "window_seconds": limits.message.window_seconds,
                            },
                        )
                        await self._warn_user(event, user_id, callback_hint=False)
                        return None

                return await handler(event, data)

            # --- UPDATE WRAPPER --------------------------------------------
            if isinstance(event, Update):
                if event.callback_query:
                    return await self.__call__(handler, event.callback_query, data)
                if event.message:
                    return await self.__call__(handler, event.message, data)

            return await handler(event, data)

        except Exception:
            logger.exception("AntiSpamMiddleware failed; allowing event to continue")
            return await handler(event, data)

    # ======================================================================
    # Duplicate callback detection
    # ======================================================================

    def _is_duplicate_callback(
        self,
        callback: CallbackQuery,
        user_id: int,
        limits: UserLimits,
        now: float,
    ) -> tuple[bool, float | None]:
        data_key = callback.data or ""
        if not data_key:
            return False, None

        fingerprints = self._callback_fingerprints[user_id]
        self._prune_old_fingerprints(fingerprints, now, limits.duplicate_window_seconds)

        last_seen = fingerprints.get(data_key)
        fingerprints[data_key] = now

        self._last_callback_data[user_id] = (data_key, now)

        if last_seen is None:
            return False, None

        return (now - last_seen) <= limits.duplicate_window_seconds, last_seen

    async def _warn_duplicate_callback(self, callback: CallbackQuery) -> None:
        try:
            await callback.answer(
                "Слишком частые нажатия, подождите немного.",
                show_alert=True,
            )
        except Exception:
            logger.debug("Failed to answer duplicate callback alert", exc_info=True)

    # ======================================================================
    # Flood detection / Limits
    # ======================================================================

    def _check_and_record(
        self,
        user_id: int,
        now: float,
        limit: RateLimit,
        storage: Dict[int, Deque[float]],
    ) -> str:
        if limit.soft_limit <= 0 or limit.hard_limit <= 0:
            return "ok"

        events = storage[user_id]
        self._prune_old(events, now, limit.window_seconds)
        events.append(now)

        if len(events) > limit.hard_limit:
            return "hard"
        if len(events) > limit.soft_limit:
            return "soft"
        return "ok"

    def _prune_old(self, timestamps: Deque[float], now: float, window: float) -> None:
        cutoff = now - window
        while timestamps and timestamps[0] < cutoff:
            timestamps.popleft()

    def _prune_old_fingerprints(
        self, fingerprints: Dict[str, float], now: float, window: float
    ) -> None:
        cutoff = now - window
        for key in list(fingerprints.keys()):
            if fingerprints[key] < cutoff:
                fingerprints.pop(key, None)

    def _is_flood_banned(self, user_id: int, now: float) -> bool:
        until = self._flood_banned_until.get(user_id)
        if until is None:
            return False
        if now >= until:
            self._flood_banned_until.pop(user_id, None)
            return False
        return True

    async def _apply_hard_limit(
        self,
        user_id: int,
        user: User | None,
        now: float,
        event: TelegramObject,
    ) -> None:
        logger.warning(
            "Anti-spam hard limit triggered",
            extra={"user_id": user_id, "event": type(event).__name__},
        )

        # Admins immune
        if user_id in {ROOT_ADMIN_ID, *ADMIN_ROOT_IDS, *ADMINS}:
            return

        # runtime limit
        self._flood_banned_until[user_id] = now + FLOOD_BAN_SECONDS

        # db-level limit
        await self._block_user_for_flood(user_id, user)

    async def _block_user_for_flood(self, user_id: int, user: User | None) -> None:
        try:
            async with async_session() as session:
                target_user = (
                    user
                    or await session.scalar(select(User).where(User.tg_id == user_id))
                )
                if not target_user:
                    return

                await block_user(
                    session,
                    user=target_user,
                    operator_admin=None,
                    confirmed=True,
                    duration=FLOOD_BAN_DURATION,
                    reason="flood",
                )
        except Exception:
            logger.exception("Failed to apply flood ban", extra={"user_id": user_id})

    # ======================================================================
    # Warnings to user
    # ======================================================================

    async def _warn_user(
        self,
        event: TelegramObject,
        user_id: int,
        *,
        callback_hint: bool,
    ) -> None:
        now = time.monotonic()
        last_warn = self._last_warning_at.get(user_id)
        if last_warn is not None and (now - last_warn) < WARNING_COOLDOWN_SECONDS:
            return

        self._last_warning_at[user_id] = now
        message_text = "Пожалуйста, не спамьте действиями — вы временно ограничены."

        if isinstance(event, CallbackQuery):
            try:
                await event.answer(
                    message_text if callback_hint else None,
                    show_alert=False,
                )
            except Exception:
                logger.debug("Failed to answer callback for spam warning", exc_info=True)
            return

        if isinstance(event, Message):
            try:
                await event.answer(message_text)
            except Exception:
                logger.debug("Failed to send spam warning", exc_info=True)
            return

    # ======================================================================
    # Helpers
    # ======================================================================

    def _extract_from_user(self, event: TelegramObject):
        if isinstance(event, Message):
            return event.from_user
        if isinstance(event, CallbackQuery):
            return event.from_user
        if isinstance(event, Update):
            if event.callback_query:
                return event.callback_query.from_user
            if event.message:
                return event.message.from_user
            if event.edited_message:
                return event.edited_message.from_user
        return getattr(event, "from_user", None)


__all__ = ["AntiSpamMiddleware", "get_user_limits"]
