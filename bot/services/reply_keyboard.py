"""Utilities for tracking reply keyboard removal/restoration."""

from __future__ import annotations

import logging
from typing import Optional

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db import Admin, User, async_session
from bot.keyboards.main_menu import main_menu

logger = logging.getLogger(__name__)


_removed_keyboards: set[int] = set()


def mark_reply_keyboard_removed(user_id: int) -> None:
    """Flag that the user's reply keyboard has been removed."""

    _removed_keyboards.add(user_id)


def clear_reply_keyboard_flag(user_id: int) -> None:
    """Clear the keyboard-removed flag for the given user."""

    _removed_keyboards.discard(user_id)


def was_reply_keyboard_removed(user_id: int) -> bool:
    """Return True if a keyboard removal was recorded for the user."""

    return user_id in _removed_keyboards


async def send_main_menu_keyboard(
    bot: Bot,
    user_id: int,
    *,
    session: Optional[AsyncSession] = None,
    text: str = "↩ Главное меню",
    reason: str | None = None,
) -> bool:
    """Send the main menu keyboard and log restoration.

    Parameters
    ----------
    bot:
        Bot instance to send the message with.
    user_id:
        Telegram user identifier.
    session:
        Optional externally managed session; a new one will be created when
        omitted.
    text:
        Message text to show above the keyboard.
    reason:
        Human-readable reason used for logging.
    """

    owns_session = False
    if session is None:
        session = async_session()
        owns_session = True

    try:
        user = await session.scalar(select(User).where(User.tg_id == user_id))
        if not user:
            logger.info("Skip keyboard restore for unknown user %s", user_id)
            clear_reply_keyboard_flag(user_id)
            return False

        is_admin = bool(
            await session.scalar(select(Admin.telegram_id).where(Admin.telegram_id == user_id))
        )

        await bot.send_message(
            user_id,
            text,
            reply_markup=main_menu(is_admin=is_admin),
        )
        logger.info(
            "Restored reply keyboard for user %s (%s)",
            user_id,
            reason or "unspecified reason",
        )
        return True
    finally:
        clear_reply_keyboard_flag(user_id)
        if owns_session:
            await session.close()