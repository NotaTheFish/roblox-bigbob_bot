"""Global handlers to block banned users before other processing."""

from __future__ import annotations

from contextlib import suppress

from aiogram import Router, types

from bot.utils.user import get_user

router = Router(name="global_block_filter")


def _is_banned(user: object) -> bool:
    return bool(getattr(user, "is_banned", False))


@router.callback_query()
async def block_banned_callback(
    callback: types.CallbackQuery,
    **data,
) -> None:
    if not callback.from_user:
        return

    user = await get_user(callback.from_user.id, data=data)
    if not user or not _is_banned(user):
        return

    if callback.message:
        with suppress(Exception):
            await callback.message.edit_reply_markup(reply_markup=None)

    with suppress(Exception):
        await callback.answer("❌ Вы заблокированы.")


@router.message()
async def block_banned_message(
    message: types.Message,
    **data,
) -> None:
    if not message.from_user:
        return

    user = await get_user(message.from_user.id, data=data)
    if not user or not _is_banned(user):
        return

    with suppress(Exception):
        await message.answer("❌ Вы заблокированы.", reply_markup=None)


__all__ = ["router"]