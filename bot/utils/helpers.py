from __future__ import annotations

from typing import Set

from sqlalchemy import select

from bot.config import ROOT_ADMIN_ID
from bot.db import Admin, async_session


async def get_admin_telegram_ids(include_root: bool = False) -> Set[int]:
    """Fetch telegram IDs of all admins.

    Args:
        include_root: Whether to include ROOT_ADMIN_ID in the result even if it is
            not stored in the database.

    Returns:
        A set containing telegram IDs of admins.
    """

    async with async_session() as session:
        admin_ids = (
            await session.scalars(
                select(Admin.telegram_id).where(Admin.telegram_id.is_not(None))
            )
        ).all()

    result = {admin_id for admin_id in admin_ids if admin_id is not None}
    if include_root and ROOT_ADMIN_ID:
        result.add(ROOT_ADMIN_ID)
    return result


__all__ = ["get_admin_telegram_ids"]