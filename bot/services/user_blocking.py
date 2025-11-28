"""Helpers for blocking and unblocking users with admin-specific checks."""

from __future__ import annotations

import logging

from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import Admin, BannedRobloxAccount, LogEntry, User
from bot.firebase.firebase_service import (
    add_ban_to_firebase,
    add_whitelist,
    remove_ban_from_firebase,
    remove_whitelist,
)


logger = logging.getLogger(__name__)


class BlockUserError(Exception):
    """Base exception for block helper errors."""


class AdminBlockPermissionError(BlockUserError):
    """Raised when a non-root admin attempts to block another admin."""


class AdminBlockConfirmationRequiredError(BlockUserError):
    """Raised when a root admin needs to confirm blocking another admin."""


async def _is_user_admin(session: AsyncSession, user: User) -> bool:
    stmt = select(Admin).where(Admin.telegram_id == user.tg_id)
    return bool(await session.scalar(stmt))


async def block_user(
    session: AsyncSession,
    *,
    user: User,
    operator_admin: Admin | None,
    confirmed: bool = False,
    duration: timedelta | None = None,
    reason: str | None = None,
    interface: str | None = None,
    operator_username: str | None = None,
) -> None:
    """Block a user while enforcing admin-specific restrictions."""

    if await _is_user_admin(session, user):
        if not operator_admin or not operator_admin.is_root:
            raise AdminBlockPermissionError
        if not confirmed:
            raise AdminBlockConfirmationRequiredError

    user.is_blocked = True
    user.blocked_until = (
        datetime.now(timezone.utc) + duration if duration else None
    )
    user.block_reason = reason
    user.ban_appeal_at = None
    user.ban_appeal_submitted = False
    user.appeal_open = False
    user.appeal_submitted_at = None
    user.ban_notified_at = None
    await _add_banned_account(session, user)

    session.add(
        LogEntry(
            event_type="security.user_blocked",
            message="Пользователь заблокирован",
            telegram_id=user.tg_id,
            user_id=user.id,
            data={
                "reason": reason,
                "operator_admin_id": operator_admin.id if operator_admin else None,
                "operator_username": operator_username,
                "interface": interface,
                "blocked_until": (
                    user.blocked_until.isoformat() if user.blocked_until else None
                ),
            },
        )
    )
    await session.commit()

    await _sync_firebase_block_state(user, blocked=True)


async def unblock_user(
    session: AsyncSession,
    *,
    user: User,
    operator_admin: Admin | None = None,
    reason: str | None = None,
    interface: str | None = None,
    operator_username: str | None = None,
) -> bool:
    """Unblock a user and reset ban-related fields."""

    removed_from_history = await _remove_banned_account(
        session, user, operator_admin=operator_admin
    )
    if not user.is_blocked and not removed_from_history:
        return False

    log_reason = reason or user.block_reason
    user.is_blocked = False
    user.blocked_until = None
    user.block_reason = None
    user.ban_appeal_at = None
    user.ban_appeal_submitted = False
    user.appeal_open = False
    user.appeal_submitted_at = None
    user.ban_notified_at = None

    session.add(
        LogEntry(
            event_type="security.user_unblocked",
            message="Пользователь разблокирован",
            telegram_id=user.tg_id,
            user_id=user.id,
            data={
                "reason": log_reason,
                "operator_admin_id": operator_admin.id if operator_admin else None,
                "operator_username": operator_username,
                "interface": interface,
            },
        )
    )
    await session.commit()

    await _sync_firebase_block_state(user, blocked=False)
    return True


def _build_banned_filters(user: User):
    filters = []
    if user.id:
        filters.append(BannedRobloxAccount.user_id == user.id)
    if user.roblox_id:
        filters.append(BannedRobloxAccount.roblox_id == user.roblox_id)
    if user.username:
        filters.append(BannedRobloxAccount.username == user.username)
    return filters


async def _add_banned_account(session: AsyncSession, user: User) -> None:
    filters = _build_banned_filters(user)
    if not filters:
        return

    stmt = select(BannedRobloxAccount).where(
        BannedRobloxAccount.unblocked_at.is_(None), or_(*filters)
    )
    banned_account = await session.scalar(stmt)
    if banned_account:
        updated = False
        if user.roblox_id and banned_account.roblox_id != user.roblox_id:
            banned_account.roblox_id = user.roblox_id
            updated = True
        if user.username and banned_account.username != user.username:
            banned_account.username = user.username
            updated = True
        if banned_account.user_id != user.id:
            banned_account.user_id = user.id
            updated = True
        if updated:
            await session.flush()
        return

    session.add(
        BannedRobloxAccount(
            user_id=user.id,
            roblox_id=user.roblox_id,
            username=user.username,
        )
    )


async def _remove_banned_account(
    session: AsyncSession, user: User, *, operator_admin: Admin | None = None
) -> bool:
    filters = _build_banned_filters(user)
    if not filters:
        return False

    stmt = select(BannedRobloxAccount).where(
        BannedRobloxAccount.unblocked_at.is_(None), or_(*filters)
    )
    result = await session.scalars(stmt)
    active_bans = list(result.all())
    if not active_bans:
        return False

    revoked_by = operator_admin.id if operator_admin else None
    now = datetime.now(timezone.utc)
    for ban in active_bans:
        if user.roblox_id and ban.roblox_id != user.roblox_id:
            ban.roblox_id = user.roblox_id
        if user.username and ban.username != user.username:
            ban.username = user.username
        if ban.user_id != user.id:
            ban.user_id = user.id
        ban.unblocked_at = now
        ban.revoked_by = revoked_by
    await session.flush()
    return True


def _normalize_roblox_id(roblox_id: str | int | None) -> str | None:
    if roblox_id is None:
        return None

    try:
        normalized = str(int(roblox_id)).strip()
    except (TypeError, ValueError):
        logger.warning("Failed to normalise roblox_id=%s", roblox_id)
        return None

    return normalized or None


async def _sync_firebase_block_state(user: User, *, blocked: bool) -> None:
    roblox_id = _normalize_roblox_id(user.roblox_id)
    if not roblox_id:
        return

    try:
        if blocked:
            success = await add_ban_to_firebase(roblox_id)
            if not success:
                logger.warning(
                    "Failed to push roblox_id=%s to Firebase bans", roblox_id
                )

            if user.verified:
                removed = await remove_whitelist(roblox_id)
                if not removed:
                    logger.warning(
                        "Failed to remove roblox_id=%s from Firebase whitelist", roblox_id
                    )
        else:
            success = await remove_ban_from_firebase(roblox_id)
            if not success:
                logger.warning(
                    "Failed to remove roblox_id=%s from Firebase bans", roblox_id
                )

            if user.verified:
                added = await add_whitelist(roblox_id)
                if not added:
                    logger.warning(
                        "Failed to add roblox_id=%s to Firebase whitelist", roblox_id
                    )
    except Exception:  # pragma: no cover - defensive logging
        logger.exception(
            "Unexpected Firebase sync error for roblox_id=%s (blocked=%s)",
            roblox_id,
            blocked,
        )


def is_block_expired(user: User) -> bool:
    """Return True if the user's block has an expiry in the past."""

    if not user.blocked_until:
        return False
    return user.blocked_until <= datetime.now(timezone.utc)


def is_user_block_active(user: User) -> bool:
    """Return True when a user's block should still be enforced."""

    return bool(user.is_blocked and not is_block_expired(user))


async def lift_expired_block(session: AsyncSession, *, user: User) -> bool:
    """Unblock users whose block expiration has elapsed."""

    if not user.is_blocked or not is_block_expired(user):
        return False

    return await unblock_user(
        session,
        user=user,
        operator_admin=None,
        reason="expired",
        interface="automatic",
    )


__all__ = [
    "AdminBlockConfirmationRequiredError",
    "AdminBlockPermissionError",
    "block_user",
    "is_user_block_active",
    "lift_expired_block",
    "unblock_user",
]