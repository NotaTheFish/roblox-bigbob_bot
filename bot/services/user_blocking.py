"""Helpers for blocking and unblocking users with admin-specific checks."""

from __future__ import annotations

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import Admin, BannedRobloxAccount, User


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
    await _add_banned_account(session, user)
    await session.commit()


async def unblock_user(session: AsyncSession, *, user: User) -> None:
    """Unblock a user and reset ban-related fields."""

    user.is_blocked = False
    user.ban_appeal_at = None
    user.ban_appeal_submitted = False
    user.appeal_open = False
    user.appeal_submitted_at = None
    user.ban_notified_at = None
    await _remove_banned_account(session, user)
    await session.commit()


def _build_banned_filters(user: User):
    filters = []
    if user.roblox_id:
        filters.append(BannedRobloxAccount.roblox_id == user.roblox_id)
    if user.username:
        filters.append(BannedRobloxAccount.username == user.username)
    if user.id:
        filters.append(BannedRobloxAccount.user_id == user.id)
    return filters


async def _add_banned_account(session: AsyncSession, user: User) -> None:
    filters = _build_banned_filters(user)
    if not filters:
        return

    stmt = select(BannedRobloxAccount).where(or_(*filters))
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


async def _remove_banned_account(session: AsyncSession, user: User) -> None:
    filters = _build_banned_filters(user)
    if not filters:
        return

    stmt = delete(BannedRobloxAccount).where(or_(*filters))
    await session.execute(stmt)


__all__ = [
    "AdminBlockConfirmationRequiredError",
    "AdminBlockPermissionError",
    "block_user",
    "unblock_user",
]