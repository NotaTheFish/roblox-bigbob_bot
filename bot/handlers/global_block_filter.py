"""Global handlers to block banned users before other processing."""

from __future__ import annotations

from contextlib import suppress
import logging

from aiogram import Router, types
from aiogram.filters import Filter
from aiogram.fsm.context import FSMContext

from bot.keyboards.ban_appeal import BAN_APPEAL_CALLBACK
from bot.states.user_states import BanAppealState
from bot.utils.user import get_user

logger = logging.getLogger(__name__)
router = Router(name="global_block_filter")


def _is_blocked(user: object) -> bool:
    return bool(getattr(user, "is_blocked", False))


class BlockedUserFilter(Filter):
    """Filter that matches only blocked users.

    If a blocked user is found, it is cached into ``data`` as ``current_user``
    to keep consistency with other middlewares.
    """

    async def __call__(self, event: types.TelegramObject, **data) -> bool | dict:
        from_user = getattr(event, "from_user", None)
        if not from_user:
            return False

        user = await get_user(from_user.id, data=data)
        if not user or not _is_blocked(user):
            return False

        if getattr(event, "data", None) == BAN_APPEAL_CALLBACK:
            return False

        if getattr(event, "message_id", None) is not None:
            state: FSMContext | None = data.get("state")
            if state:
                current_state = await state.get_state()
                if current_state == BanAppealState.waiting_for_message.state:
                    return False

        if data is not None and "current_user" not in data:
            data["current_user"] = user

        return {"blocked_user": user}


@router.callback_query(BlockedUserFilter())
async def block_banned_callback(
    callback: types.CallbackQuery,
    blocked_user: object,
    **data,
) -> None:
    if callback.message:
        with suppress(Exception):
            await callback.message.edit_reply_markup(reply_markup=None)

    with suppress(Exception):
        await callback.answer("❌ Вы заблокированы.")

    logger.info("Blocked callback from user %s intercepted and halted.", blocked_user.tg_id)


@router.message(BlockedUserFilter())
async def block_banned_message(
    message: types.Message,
    blocked_user: object,
    **data,
) -> None:
    with suppress(Exception):
        await message.answer("❌ Вы заблокированы.", reply_markup=None)

    logger.info("Blocked message from user %s intercepted and halted.", blocked_user.tg_id)


__all__ = ["router", "BlockedUserFilter"]