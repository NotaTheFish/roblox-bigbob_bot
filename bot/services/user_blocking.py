"""Helpers for blocking and unblocking users with admin-specific checks."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import Admin, User


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
) -> None:
    """Block a user while enforcing admin-specific restrictions."""

    if await _is_user_admin(session, user):
        if not operator_admin or not operator_admin.is_root:
            raise AdminBlockPermissionError
        if not confirmed:
            raise AdminBlockConfirmationRequiredError

    user.is_blocked = True
    user.ban_appeal_at = None
    user.ban_appeal_submitted = False
    user.appeal_open = False
    user.appeal_submitted_at = None
    user.ban_notified_at = None
    await session.commit()


async def unblock_user(session: AsyncSession, *, user: User) -> None:
    """Unblock a user and reset ban-related fields."""

    user.is_blocked = False
    user.ban_appeal_at = None
    user.ban_appeal_submitted = False
    user.appeal_open = False
    user.appeal_submitted_at = None
    user.ban_notified_at = None
    await session.commit()


__all__ = [
    "AdminBlockConfirmationRequiredError",
    "AdminBlockPermissionError",
    "block_user",
    "unblock_user",
]