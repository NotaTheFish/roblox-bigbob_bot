from __future__ import annotations

import logging

from sqlalchemy import select

from bot.config import ROOT_ADMIN_ID
from bot.db import Admin, async_session

logger = logging.getLogger(__name__)


async def is_admin(uid: int) -> bool:
    """Return whether the given Telegram user id has admin privileges.

    The root admin always has access even if no corresponding DB record exists.
    """

    if ROOT_ADMIN_ID and uid == ROOT_ADMIN_ID:
        logger.debug(
            "Granting root admin access without DB lookup", extra={"user_id": uid}
        )
        return True

    async with async_session() as session:
        has_entry = bool(
            await session.scalar(select(Admin).where(Admin.telegram_id == uid))
        )
        logger.debug("Admin DB lookup result", extra={"user_id": uid, "has_entry": has_entry})
        return has_entry