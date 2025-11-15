"""Reusable filter ensuring the current user is not banned."""

from __future__ import annotations

from typing import Any, Dict

from aiogram.filters import BaseFilter
from aiogram.types import TelegramObject


class NotBannedFilter(BaseFilter):
    """Filter out updates coming from banned users.

    The filter relies on ``current_user`` provided via middleware and checks the
    ``is_banned`` flag (falling back to ``is_blocked`` for backward
    compatibility). If no user object is available, the update is allowed to
    proceed so that other parts of the system may handle registration flows.
    """

    async def __call__(self, event: TelegramObject, data: Dict[str, Any]) -> bool:
        current_user = data.get("current_user")
        if not current_user:
            return True

        is_banned = getattr(current_user, "is_banned", None)
        if is_banned is None:
            is_banned = getattr(current_user, "is_blocked", None)

        return not bool(is_banned)


__all__ = ["NotBannedFilter"]