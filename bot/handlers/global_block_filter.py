"""Global handlers to block banned users before other processing."""

from __future__ import annotations

from contextlib import suppress
import logging

from aiogram import Router, types

from bot.utils.user import get_user

logger = logging.getLogger(__name__)
router = Router(name="global_block_filter")


def _is_blocked(user: object) -> bool:
    return bool(getattr(user, "is_blocked", False))


@router.callback_query()
async def block_banned_callback(
    callback: types.CallbackQuery,
    **data,
) -> None:
    if not callback.from_user:
        return

    user = await get_user(callback.from_user.id, data=data)
    if not user or not _is_blocked(user):
        return

    if callback.message:
        with suppress(Exception):
            await callback.message.edit_reply_markup(reply_markup=None)

    with suppress(Exception):
        await callback.answer("❌ Вы заблокированы.")

    logger.info("Blocked callback from user %s intercepted and halted.", callback.from_user.id)


@router.message()
async def block_banned_message(
    message: types.Message,
    **data,
) -> None:
    if not message.from_user:
        return

    user = await get_user(message.from_user.id, data=data)
    if not user or not _is_blocked(user):
        return

    with suppress(Exception):
        await message.answer("❌ Вы заблокированы.", reply_markup=None)

    logger.info("Blocked message from user %s intercepted and halted.", message.from_user.id)


__all__ = ["router"]